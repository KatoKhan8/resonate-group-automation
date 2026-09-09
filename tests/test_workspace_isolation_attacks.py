"""Adversarial tenancy: what one client can actually reach of another's.

Existing coverage asserts that the boundary works when it is used. This
file asks the opposite question - what happens when somebody deliberately
reaches past it - and it is written to be readable as a report: every test
is named for the attack, and every docstring says BLOCKED (naming the
guard) or LEAKED (naming the code path that permitted it).

The estate is two synthetic clients, `alpha` and `bravo`, in a throwaway
directory. `store.use_directory` moves the queue, the campaign file, the
workspace table, the audit log and the sender roster together, and
`CLIENTS_DIR` moves the client configs, so nothing here can read, shadow
or write a real client's state.

A test that documents a leak asserts the leak. That is deliberate: a
characterisation test is the only kind that fails when somebody fixes the
hole, which is exactly when this file should be re-read.
"""
import os
import shutil
import tempfile
import unittest

from src import approve as approve_mod
from src import assignment
from src import campaigns as campaign_store
from src import clients
from src import events
from src import repo as repo_module
from src import senderidentity as si
from src import store
from src import workspaces as ws

ALPHA = "alpha"
BRAVO = "bravo"

ALPHA_OPS = "ops@alpha.test"
BRAVO_OPS = "ops@bravo.test"
ROOT = "root@resonate.test"

CONFIG = """\
name: {name}
domain: {slug}.test
booking_link: https://{slug}.test/book

sender:
  mode: client_rep
  name: {name} Sender
  title: Head of Outreach
  email: sender@{slug}.test

market:
  must: a services business that tracks time
  size_min_employees: 10
  geos: [United Kingdom]
  flag_dont_drop: true

personas:
  champion:
    titles: [Operations Manager]
    cap_per_domain: 1
    angles:
      ops: utilisation, capacity planning
"""


def a_record(rid, client, email=None, contact_key=None):
    """A well-formed queue record. `store.validate` accepts it."""
    key = contact_key or f"{rid}-c1"
    return {
        "id": rid, "lane": "cold", "client": client, "company": rid.upper(),
        "domain": f"{rid}.test", "state": "queued", "drop_reason": None,
        "log": [], "events": [],
        "contacts": [{
            "key": key, "name": "Pat Person", "title": "Operations Manager",
            "email": email or f"pat@{rid}.test", "persona": "champion",
            "selected": True, "verified": True,
        }],
    }


class Estate(unittest.TestCase):
    """Two clients, two workspaces, three users, in a temp directory."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-isolation-")
        self._prev = {k: os.environ.get(k) for k in
                      ("QUEUE", "OUT", "CLIENTS_DIR") + store.STATE_OVERRIDES}
        store.use_directory(os.path.join(self.tmp, "work"))
        os.environ["OUT"] = os.path.join(self.tmp, "out")
        os.environ["CLIENTS_DIR"] = os.path.join(self.tmp, "clients")
        os.makedirs(os.environ["CLIENTS_DIR"], exist_ok=True)
        # The one assertion that makes every other one meaningful: nothing
        # below is touching the real work/ directory.
        self.assertTrue(store.queue_path().startswith(os.path.abspath(self.tmp)))

        for slug, name in ((ALPHA, "Alpha"), (BRAVO, "Bravo")):
            with open(os.path.join(os.environ["CLIENTS_DIR"], f"{slug}.yaml"),
                      "w", encoding="utf-8") as f:
                f.write(CONFIG.format(slug=slug, name=name))

        ws.ensure(ALPHA, "Alpha", ALPHA)
        ws.ensure(BRAVO, "Bravo", BRAVO)
        ws.add_user(ALPHA_OPS, "Alpha Ops")
        ws.add_user(BRAVO_OPS, "Bravo Ops")
        ws.add_user(ROOT, "Root", super_admin=True)
        ws.assign(ALPHA_OPS, ALPHA, ws.WORKSPACE_ADMIN)
        ws.assign(BRAVO_OPS, BRAVO, ws.WORKSPACE_ADMIN)

        store.append([a_record("alpha-1", ALPHA), a_record("bravo-1", BRAVO)])

        campaign_store.save([
            dict(campaign_store.new_campaign("alpha-c1", ALPHA, "Alpha One"),
                 record_ids=["alpha-1"]),
            dict(campaign_store.new_campaign("bravo-c1", BRAVO, "Bravo One"),
                 record_ids=["bravo-1"]),
        ])

        si.install([
            si.new_sender(ALPHA, "anna", "Anna Alpha"),
            si.new_email_account(ALPHA, "anna-01", "anna", "anna01@alpha.test",
                                 provider_account_id="p-100"),
            si.new_sender(BRAVO, "boris", "Boris Bravo"),
            si.new_email_account(BRAVO, "boris-01", "boris", "b01@bravo.test",
                                 provider_account_id="p-100"),
        ])

        self.a = repo_module.Repo.for_user(ALPHA_OPS, ALPHA)
        self.b = repo_module.Repo.for_user(BRAVO_OPS, BRAVO)

    def tearDown(self):
        for k, v in self._prev.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.tmp, ignore_errors=True)


# ------------------------------------------------------------------ attack 1

class ReadingTheOtherClientsRecords(Estate):
    """1. `Repo.for_client("alpha").records()` and every other read."""

    def test_records_returns_only_this_clients_rows(self):
        """BLOCKED - src/repo.py:208 filters every row through `_mine`."""
        cli = repo_module.Repo.for_client(ALPHA)
        self.assertEqual([r["id"] for r in cli.records()], ["alpha-1"])
        self.assertEqual([r["id"] for r in self.a.records()], ["alpha-1"])
        # And the estate really does hold both, so the filter is doing work.
        self.assertEqual(sorted(r["id"] for r in store.load()),
                         ["alpha-1", "bravo-1"])

    def test_every_read_on_the_repo_is_scoped(self):
        """BLOCKED - `_mine` (src/repo.py:193) is on all six read paths."""
        self.assertEqual(self.a.batches(), {})
        self.assertEqual([c["campaign_id"] for c in self.a.campaigns()],
                         ["alpha-c1"])
        self.assertEqual(self.a.stats()["records"], 1)
        self.assertEqual([r["id"] for r in self.a.records(state="queued")],
                         ["alpha-1"])

    def test_only_admin_repo_is_unscoped_and_it_is_named(self):
        """BLOCKED by construction - the widening constructor is `admin_repo`.

        There is no way to widen a Repo after construction: `client` is set
        in `__init__` and nothing reassigns it.
        """
        self.assertEqual(len(repo_module.admin_repo().records()), 2)
        self.assertIsNone(repo_module.admin_repo().client)


# ------------------------------------------------------------------ attack 2

class PassingTheOtherClientsRecordId(Estate):
    """2. Naming B's record id to a repo scoped to A."""

    def test_record_by_id_raises_rather_than_returning_none(self):
        """BLOCKED - `_guard` (src/repo.py:196-202) raises CrossClientAccess."""
        with self.assertRaises(repo_module.CrossClientAccess):
            self.a.record("bravo-1")
        with self.assertRaises(repo_module.CrossClientAccess):
            self.a.contact("bravo-1", "bravo-1-c1")

    def test_an_absent_id_is_a_different_answer_from_a_foreign_one(self):
        """BLOCKED, and the distinction is deliberate at src/repo.py:57-63.

        Absent returns None; foreign raises. The web layer turns both into
        404 - `tests/test_tenancy_disclosure.py` holds that half - but the
        service layer keeps them apart so an audit entry can say which.
        """
        self.assertIsNone(self.a.record("no-such-record"))
        with self.assertRaises(repo_module.CrossClientAccess):
            self.a.record("bravo-1")

    def test_writing_a_foreign_record_is_refused(self):
        """BLOCKED - src/repo.py:263-267 checks every row before the write."""
        foreign = store.get("bravo-1")
        with self.assertRaises(repo_module.CrossClientAccess):
            self.a.save_records([foreign])
        self.assertEqual(len(store.load()), 2)


# ------------------------------------------------------------------ attack 3

class UsingTheOtherWorkspacesSender(Estate):
    """3. `senderidentity.sender`, `account`, `require_sender`."""

    def test_sender_from_another_workspace_raises(self):
        """BLOCKED - src/senderidentity.py:275-276 raises CrossWorkspaceSender."""
        with self.assertRaises(si.CrossWorkspaceSender):
            si.sender(ALPHA, "boris")
        with self.assertRaises(si.CrossWorkspaceSender):
            si.require_sender(ALPHA, "boris")

    def test_account_from_another_workspace_raises(self):
        """BLOCKED - src/senderidentity.py:327-328."""
        with self.assertRaises(si.CrossWorkspaceSender):
            si.account(ALPHA, si.EMAIL, "boris-01")

    def test_an_unknown_sender_is_absent_not_foreign(self):
        """BLOCKED, and the two answers stay distinguishable."""
        self.assertIsNone(si.sender(ALPHA, "nobody"))
        with self.assertRaises(si.UnknownSender):
            si.require_sender(ALPHA, "nobody")

    def test_a_shared_provider_account_id_does_not_cross(self):
        """BLOCKED - src/senderidentity.py:342 resolves inside one workspace.

        Both fixtures deliberately carry `provider_account_id = p-100`. A
        provider's id space is not ours and offers no cross-tenant
        uniqueness, so resolving one globally would be a walk from a
        HeyReach id to another client's roster.
        """
        self.assertEqual(
            si.by_provider_account(ALPHA, si.EMAIL, "p-100")["account_id"],
            "anna-01")
        self.assertEqual(
            si.by_provider_account(BRAVO, si.EMAIL, "p-100")["account_id"],
            "boris-01")

    def test_deactivating_another_workspaces_sender_changes_nothing(self):
        """BLOCKED - src/senderidentity.py:596 matches on workspace too."""
        with self.assertRaises(si.UnknownSender):
            si.set_active(ALPHA, si.SENDER, "boris", False)
        self.assertTrue(si.sender(BRAVO, "boris")["active"])

    def test_the_roster_and_the_digest_are_scoped(self):
        """BLOCKED - `_rows` (src/senderidentity.py:140-143) has no unscoped
        variant, so every derived view inherits the scope."""
        roster = si.roster(ALPHA)
        self.assertEqual([s["sender_id"] for s in roster["senders"]], ["anna"])
        self.assertNotEqual(si.digest(ALPHA), si.digest(BRAVO))


# ------------------------------------------------------------------ attack 4

class ReassigningToTheOtherWorkspacesSender(Estate):
    """4. `assignment.reassign` with a sender that is not ours."""

    def test_reassign_to_a_foreign_sender_is_refused(self):
        """BLOCKED - src/assignment.py:246 calls `si.require_sender`, which
        raises CrossWorkspaceSender before anything is written."""
        rec = self.a.record("alpha-1")
        contact = rec["contacts"][0]
        with self.assertRaises(si.CrossWorkspaceSender):
            assignment.reassign(rec, contact, ALPHA, si.EMAIL, "boris",
                                by=ALPHA_OPS, reason="attack",
                                config=self.a.config())
        self.assertEqual(contact.get("sender_assignment"), None)

    def test_the_api_binds_the_workspace_to_the_repo(self):
        """BLOCKED at the call site - src/web/api.py:630 passes
        `repo.workspace`, never a workspace from the request.

        This asserts the property that makes the primitive safe, rather
        than the source text: the repo's workspace is the membership's
        workspace and a caller cannot move it.
        """
        self.assertEqual(self.a.workspace, ALPHA)
        self.assertEqual(self.a.membership["workspace"], ALPHA)
        with self.assertRaises(ws.NotAMember):
            repo_module.Repo.for_user(ALPHA_OPS, BRAVO)

    def test_LEAK_the_primitive_itself_never_checks_record_against_workspace(self):
        """LEAKED (defence in depth) - src/assignment.py:229-241.

        `reassign(rec, contact, workspace, ...)` takes the record and the
        workspace as two independent arguments and never asks whether the
        record belongs to that workspace. Hand it A's record and B's
        workspace and B's inbox is stamped onto A's contact, with B's
        provider account id, and `store.log` records it as ordinary.

        Nothing in the product does this - `api.reassign_sender` binds
        both to one Repo - so the boundary holds today. It holds because
        of one line at one call site, not because the primitive refuses.
        """
        rec = self.a.record("alpha-1")
        contact = rec["contacts"][0]
        entry = assignment.reassign(rec, contact, BRAVO, si.EMAIL, "boris",
                                    by=ALPHA_OPS, reason="forged workspace",
                                    config=self.b.config())
        self.assertEqual(entry["to"]["sender_id"], "boris")
        stored = contact["sender_assignment"][si.EMAIL]
        self.assertEqual(stored["address"], "b01@bravo.test")
        self.assertEqual(stored["workspace"], BRAVO)


# ------------------------------------------------------------------ attack 5

class ReachingTheOtherClientsCampaign(Estate):
    """5. `campaigns.get`, `require`, `by_record`."""

    def test_repo_campaign_refuses_a_foreign_id(self):
        """BLOCKED - src/repo.py:245-249 guards the row it found."""
        with self.assertRaises(repo_module.CrossClientAccess):
            self.a.campaign("bravo-c1")
        self.assertIsNone(self.a.campaign("no-such-campaign"))

    def test_the_module_level_getters_are_unscoped_by_design(self):
        """BLOCKED at the boundary, not in the function.

        `campaigns.get` and `campaigns.require` take no client and return
        anybody's row. They are the CLI's and the store's primitives; the
        tenancy boundary is `Repo.campaign`. Asserted here so the shape of
        the guarantee is written down: these two are safe only while no
        request path calls them with a caller-supplied id.
        """
        self.assertEqual(campaign_store.get("bravo-c1")["client"], BRAVO)
        self.assertEqual(campaign_store.require("bravo-c1")["client"], BRAVO)

    def test_writing_a_foreign_campaign_is_refused(self):
        """BLOCKED - src/repo.py:277-279."""
        with self.assertRaises(repo_module.CrossClientAccess):
            self.a.save_campaign(campaign_store.get("bravo-c1"))

    def test_stealing_a_campaign_id_is_refused(self):
        """BLOCKED - src/repo.py:283-285.

        A campaign that claims to be A's but reuses B's id would otherwise
        overwrite B's row on the id match.
        """
        theft = dict(campaign_store.new_campaign("bravo-c1", ALPHA, "Mine now"))
        with self.assertRaises(repo_module.CrossClientAccess):
            self.a.save_campaign(theft)
        self.assertEqual(campaign_store.get("bravo-c1")["client"], BRAVO)

    def test_a_campaign_may_not_claim_another_clients_record_ids(self):
        """LEAKED - src/repo.py:275-290 checks the campaign's `client` and
        never its `record_ids`, and `campaigns.by_record` (src/campaigns.py:
        302-328) is unscoped.

        So B may save a campaign of B's own that lists A's records, and
        `by_record` then answers about A's records to every caller that
        asks - including `approve.pending` (src/approve.py:232) and
        `push.collect`, which build A's cadence from what it says.

        Both directions are damage. An A record in no campaign of its own
        is claimed outright and runs B's step graph. An A record that *is*
        in an A campaign becomes ambiguous, and src/campaigns.py:326 maps
        an ambiguous record to `None` - so B silently detaches A's records
        from A's own campaign and drops them back to the default cadence.
        The reviewer in A sees a different set of steps and nothing in A's
        workspace explains why: `repo.campaign` refuses to show them the
        row that did it.

        B still cannot *read* A's records - `campaign_detail` intersects
        with `repo.records()`. What B gains is control over A's sequencing.
        """
        with store.transaction() as rows:
            rows.append(a_record("alpha-2", ALPHA))

        before = campaign_store.by_record()
        self.assertEqual(before["alpha-1"]["campaign_id"], "alpha-c1")
        self.assertNotIn("alpha-2", before)

        grab = dict(campaign_store.new_campaign("bravo-c2", BRAVO, "Grab"),
                    record_ids=["alpha-1", "alpha-2"])
        # FIXED. `save_campaign` checked whose campaign it was and never which
        # records it claimed. It refuses now, and says how many.
        with self.assertRaises(repo_module.CrossClientAccess) as raised:
            self.b.save_campaign(grab)
        self.assertIn("another client", str(raised.exception))

        after = campaign_store.by_record()
        # Nothing moved: A's record is still in A's campaign, and the
        # unclaimed one is still unclaimed.
        self.assertEqual(after["alpha-1"]["campaign_id"], "alpha-c1")
        self.assertNotIn("alpha-2", after)
        self.assertEqual([c["campaign_id"] for c in self.b.campaigns()],
                         ["bravo-c1"])

    def test_a_campaign_may_not_claim_a_record_that_does_not_exist(self):
        """An id that is merely absent today is one somebody may be given
        tomorrow, so an unknown id is refused rather than reserved."""
        ghost = dict(campaign_store.new_campaign("bravo-c3", BRAVO, "Ghost"),
                     record_ids=["nobody-has-this-id"])
        with self.assertRaises(repo_module.CrossClientAccess):
            self.b.save_campaign(ghost)


# ------------------------------------------------------------------ attack 6

class ConsumingAnApprovalGrantedElsewhere(Estate):
    """6. An approval is a fact on a record, so reaching it means reaching
    the record."""

    def approve_bravo(self):
        rec = self.b.record("bravo-1")
        rec["approvals"] = {"bravo-1-c1": {"s1": {
            "by": BRAVO_OPS, "at": store.now(), "fingerprint": "x"}}}
        self.b.save_records([rec])
        return rec

    def test_an_approval_is_unreachable_because_its_record_is(self):
        """BLOCKED - src/repo.py:220 and src/repo.py:222-229.

        `approval.stored` reads `rec["approvals"]`, so there is no approval
        object with its own identity to reach for; A must first hold B's
        record, and it cannot.
        """
        self.approve_bravo()
        with self.assertRaises(repo_module.CrossClientAccess):
            self.a.record("bravo-1")
        with self.assertRaises(repo_module.CrossClientAccess):
            self.a.contact("bravo-1", "bravo-1-c1")

    def test_a_scoped_approval_queue_contains_nothing_foreign(self):
        """BLOCKED - `approve.pending` is given `repo.records()` at
        src/web/api.py:2934, and that list is already filtered."""
        self.approve_bravo()
        pending = approve_mod.pending(self.a.records())
        ids = {row["id"] for row in pending["waiting"] + pending["blocked"]}
        self.assertNotIn("bravo-1", ids)

    def test_the_unscoped_default_reads_the_whole_estate(self):
        """BLOCKED at the boundary, not in the function - and worth naming.

        `approve.pending()` with no argument defaults to `store.load()`
        (src/approve.py:225). It is the CLI's default. A handler that
        called it without `repo.records()` would render both tenants'
        queues on one screen and nothing in the function would object.
        """
        everything = approve_mod.pending()
        ids = {row["id"] for row in
               everything["waiting"] + everything["blocked"]}
        self.assertEqual(ids & {"alpha-1", "bravo-1"}, {"alpha-1", "bravo-1"})


# ------------------------------------------------------------------ attack 7

class SeeingTheOtherClientsRepliesAndEvents(Estate):
    """7. Replies and events, which live on the record."""

    def a_reply_on(self, record_id, contact_key):
        rec = store.get(record_id)
        events.record(rec, events.REPLY_RECEIVED, contact_key=contact_key,
                      channel="email", provider="emailbison",
                      provider_event_id=f"emailbison:{record_id}")
        with store.transaction() as rows:
            for i, row in enumerate(rows):
                if row["id"] == record_id:
                    rows[i] = rec
        return rec

    def test_a_reply_is_invisible_across_the_boundary(self):
        """BLOCKED - an event is a list on the record, so `repo.records()`
        (src/repo.py:206-216) is the only door and it is filtered."""
        self.a_reply_on("bravo-1", "bravo-1-c1")
        seen = [e for rec in self.a.records() for e in rec.get("events") or []]
        self.assertEqual(seen, [])
        self.assertEqual(
            len(events.of(store.get("bravo-1"), events.REPLY_RECEIVED)), 1)

    def test_an_event_naming_the_wrong_client_is_refused(self):
        """BLOCKED - src/events.py:386-388 compares the event's client with
        the record's and reports `unmatched` rather than applying."""
        recs = store.load()
        out = events.apply(recs, events.neutral(
            type=events.REPLY_RECEIVED, channel="email", provider="emailbison",
            provider_event_id="emailbison:forged-1",
            record_id="alpha-1", client=BRAVO))
        self.assertEqual(out["status"], "unmatched")
        self.assertEqual(out["why"], "client does not match the record")

    def test_an_event_with_no_client_is_refused_when_the_address_is_shared(self):
        """FIXED - `match_record` now refuses an ambiguous address.

        Was LEAKED. `src/events.py` gates the tenancy comparison on
        `if event.get("client") and ...`, so a falsy client skipped it, and

        A falsy client skips the tenancy comparison entirely, and matching
        falls through to `match_record`'s address scan (src/events.py:321-
        325), which walks the *whole* estate and returns the first record
        holding that address.

        This is not a hypothetical shape. `adapters.from_emailbison` reads
        the client out of the provider's custom variables
        (src/adapters.py:97), and `src/events.py:326-329` records that
        HeyReach's custom fields "come back empty from both the inbox and
        /lead/GetLead" - so a LinkedIn reply normally arrives with no
        client at all. `poller.run` then hands `inbound.ingest` the entire
        queue (src/poller.py:388, `recs=None`).

        Here both tenants hold the same decision maker - two agencies'
        clients selling to one person is ordinary - and B's reply is
        applied to A's record: A's company is paused, A's log gains an
        entry, and A's reviewer is shown a reply that was never theirs.
        """
        with store.transaction() as rows:
            for row in rows:
                row["contacts"][0]["email"] = "shared@target.test"

        recs = store.load()
        self.assertEqual([r["id"] for r in recs], ["alpha-1", "bravo-1"])
        out = events.apply(recs, events.neutral(
            type=events.REPLY_RECEIVED, channel="email", provider="heyreach",
            provider_event_id="heyreach:9", client=None,
            email="shared@target.test"))

        # The address belongs to two tenants, so it identifies neither.
        # Refused rather than attached to whichever record came first.
        self.assertEqual(out["status"], "unmatched")
        self.assertNotEqual(out.get("record_id"), "alpha-1")
        self.assertFalse(out.get("paused"))
        # And nobody was paused as a side effect.
        self.assertEqual([r.get("paused") for r in store.load()], [None, None])


# ------------------------------------------------------------------ attack 8

class ARecordWithNoClient(Estate):
    """8. Who owns a row whose `client` is missing or null?"""

    def orphan(self, value=None, omit=False):
        rec = a_record("orphan-1", ALPHA)
        if omit:
            rec.pop("client")
        else:
            rec["client"] = value
        with store.transaction() as rows:
            rows.append(rec)
        return rec

    def test_nobody_owns_it_and_only_the_admin_repo_sees_it(self):
        """BLOCKED, fail-closed - src/repo.py:193-194.

        `_mine` compares for equality, so `None == "alpha"` is False for
        every scoped repo. An unowned row is therefore invisible to every
        tenant and visible only to `admin_repo`, which is the conservative
        answer: it is quarantined rather than shared.
        """
        self.orphan(omit=True)
        self.assertNotIn("orphan-1", [r["id"] for r in self.a.records()])
        self.assertNotIn("orphan-1", [r["id"] for r in self.b.records()])
        self.assertIn("orphan-1",
                      [r["id"] for r in repo_module.admin_repo().records()])
        with self.assertRaises(repo_module.CrossClientAccess):
            self.a.record("orphan-1")

    def test_no_tenant_can_adopt_it(self):
        """BLOCKED - src/repo.py:263-267 refuses the write both ways."""
        self.orphan(value=None)
        rec = store.get("orphan-1")
        with self.assertRaises(repo_module.CrossClientAccess):
            self.a.save_records([rec])
        # And claiming it by rewriting the field is refused for the same
        # reason the row was invisible: the repo checks the row it was
        # given, so A may only write rows already stamped `alpha`.
        self.assertIsNone(store.get("orphan-1").get("client"))

    def test_LEAK_the_sanctioned_write_path_accepts_a_null_client(self):
        """LEAKED (weakly) - src/store.py:249-261.

        `validate` checks that the key `client` is *present*, never that it
        holds a client. `client: None` therefore passes `store.append`, the
        one guarded ingestion path, and creates a row no tenant owns and no
        tenant can repair - only `admin_repo` can see it, and only a hand
        edit can re-tenant it.

        Fail-closed, so not a disclosure. It is an orphaning bug: a record
        that cost credits becomes unreachable from the product.
        """
        rec = a_record("orphan-2", ALPHA)
        rec["client"] = None
        store.append([rec])                            # accepted
        self.assertEqual(store.validate(rec), [])
        self.assertIsNone(store.get("orphan-2")["client"])
        self.assertNotIn("orphan-2", [r["id"] for r in self.a.records()])

    def test_an_unowned_row_still_absorbs_an_unscoped_event(self):
        """LEAKED, as a consequence of attack 7.

        The row is unreachable from every workspace, but `events.apply`
        does not use a Repo, so an address match still writes to it. State
        nobody can read keeps changing.
        """
        self.orphan(omit=True)
        recs = store.load()
        out = events.apply(recs, events.neutral(
            type=events.REPLY_RECEIVED, channel="email", provider="heyreach",
            provider_event_id="heyreach:10", email="pat@orphan-1.test"))
        self.assertEqual(out["status"], "applied")
        self.assertEqual(out["record_id"], "orphan-1")


# ------------------------------------------------------------------ attack 9

class TheClientChangesMidFlight(Estate):
    """9. A record re-tenanted underneath a repo that is holding it."""

    def test_rewriting_the_field_on_the_way_out_is_refused(self):
        """BLOCKED - src/repo.py:263-267 checks the row as submitted."""
        rec = self.a.record("alpha-1")
        rec["client"] = BRAVO
        with self.assertRaises(repo_module.CrossClientAccess):
            self.a.save_records([rec])
        self.assertEqual(store.get("alpha-1")["client"], ALPHA)

    def test_a_foreign_row_cannot_be_smuggled_in_beside_a_valid_one(self):
        """BLOCKED - the loop at src/repo.py:264 checks every element."""
        mine = self.a.record("alpha-1")
        theirs = store.get("bravo-1")
        with self.assertRaises(repo_module.CrossClientAccess):
            self.a.save_records([mine, theirs])

    def test_a_stale_write_after_a_re_tenanting_is_refused(self):
        """LEAKED - src/repo.py:268-273.

            by_id = {r["id"]: r for r in records}
            for i, existing in enumerate(rows):
                if existing["id"] in by_id and self._mine(existing):
                    rows[i] = by_id.pop(existing["id"])
            rows.extend(by_id.values())

        `pop` happens only inside the `if`. When the stored row has been
        re-tenanted to B, `_mine(existing)` is False, the id is never
        popped, and the stale copy is *appended* - so the queue ends up
        with two rows carrying one id: B's live record and A's shadow of
        it.

        Two consequences. A keeps a full copy of a record that was moved
        away, including whatever B has since added to A's stale view - so
        a re-tenanting is not a transfer, it is a fork. And `store.get`
        returns the first match, which is now B's row, so A cannot even
        read back the row it just wrote: `repo.record` raises
        CrossClientAccess on A's own write.

        `store.append` refuses a duplicate id (src/store.py:305-306);
        `store.transaction`, which this uses, does not check.
        """
        stale = self.a.record("alpha-1")
        stale["company"] = "A KNEW THIS"

        # An administrator moves the record to the other tenant.
        with store.transaction() as rows:
            for row in rows:
                if row["id"] == "alpha-1":
                    row["client"] = BRAVO

        # FIXED. The id was popped only inside the `_mine` branch, so a row
        # that had moved was left behind and then appended - two rows sharing
        # one id, and `store.get` finding the other tenant's first, so A could
        # not read back its own write. A re-tenanting is a transfer, not a
        # fork: refused, and the caller re-reads.
        with self.assertRaises(repo_module.CrossClientAccess) as raised:
            self.a.save_records([stale])
        self.assertIn("re-read", str(raised.exception))

        copies = [r for r in store.load() if r["id"] == "alpha-1"]
        self.assertEqual(len(copies), 1)
        self.assertEqual(copies[0]["client"], BRAVO)
        self.assertNotEqual(copies[0]["company"], "A KNEW THIS")
        self.assertEqual(self.a.records(), [])


# ----------------------------------------------------------------- attack 10

class AMemberOfOneWorkspaceAskingForAnother(Estate):
    """10. `Repo.for_user` with a membership that does not cover it."""

    def test_for_user_refuses_a_workspace_the_member_is_not_in(self):
        """BLOCKED - src/repo.py:136 calls `workspaces.require_member`, which
        raises NotAMember at src/workspaces.py:298-300."""
        with self.assertRaises(ws.NotAMember):
            repo_module.Repo.for_user(ALPHA_OPS, BRAVO)
        with self.assertRaises(ws.NotAMember):
            repo_module.Repo.for_user(BRAVO_OPS, ALPHA)

    def test_the_refusal_does_not_reveal_that_the_workspace_exists(self):
        """BLOCKED - src/workspaces.py:299 uses one message for both cases.

        "not yours" and "no such thing" have to be indistinguishable, or
        the refusal is an oracle for which tenants exist.
        """
        try:
            repo_module.Repo.for_user(ALPHA_OPS, BRAVO)
        except ws.NotAMember as e:
            real = str(e)
        try:
            repo_module.Repo.for_user(ALPHA_OPS, "nosuchworkspace")
        except ws.NotAMember as e:
            fake = str(e)
        self.assertEqual(real.replace(BRAVO, "X"),
                         fake.replace("nosuchworkspace", "X"))

    def test_a_repo_with_no_membership_carries_no_permissions(self):
        """BLOCKED - src/repo.py:153-156.

        `Repo.for_client` is the CLI's constructor. If one ever reached a
        request path, `require` refuses rather than waving it through,
        because a repo with no membership behind it has nobody to check.
        """
        cli = repo_module.Repo.for_client(ALPHA)
        self.assertIsNone(cli.membership)
        self.assertFalse(cli.may(ws.WORKSPACE_VIEW))
        with self.assertRaises(ws.NotPermitted):
            cli.require(ws.WORKSPACE_VIEW)

    def test_a_role_cannot_carry_a_permission_it_was_not_granted(self):
        """BLOCKED - src/workspaces.py:303-308, on top of the tenancy check."""
        ws.add_user("viewer@alpha.test", "Viewer")
        ws.assign("viewer@alpha.test", ALPHA, ws.VIEWER)
        viewer = repo_module.Repo.for_user("viewer@alpha.test", ALPHA)
        self.assertTrue(viewer.may(ws.WORKSPACE_VIEW))
        with self.assertRaises(ws.NotPermitted):
            viewer.require(ws.CONTACTS_EXPORT)
        with self.assertRaises(ws.NotPermitted):
            viewer.require(ws.OPERATIONS_VIEW)

    def test_removing_a_membership_closes_the_workspace_immediately(self):
        """BLOCKED - `for_user` re-reads the table on every construction, so
        there is no cached grant to outlive the removal."""
        ws.remove(ALPHA_OPS, ALPHA)
        with self.assertRaises(ws.NotAMember):
            repo_module.Repo.for_user(ALPHA_OPS, ALPHA)

    def test_two_workspaces_cannot_be_pointed_at_one_client(self):
        """BLOCKED - src/workspaces.py:1014-1020 raises ClientTaken.

        This is the tenancy hole that is not about ids at all: two
        workspaces sharing a client file share every record and every
        campaign while keeping separate audit trails.
        """
        with self.assertRaises(ws.ClientTaken):
            ws.ensure("alpha-shadow", "Shadow", ALPHA)
        # And the second reader agrees: `clients.overrides_for` refuses an
        # estate where two workspaces claim one client.
        self.assertEqual(clients.overrides_for(ALPHA), {})


# ----------------------------------------------------------------- attack 11

class TheSuperAdminCrossing(Estate):
    """11. Is a super admin's crossing named in the log, or invisible?"""

    def test_the_crossing_is_allowed_and_the_membership_says_so(self):
        """BLOCKED-by-design, and recorded in memory.

        `membership_of` (src/workspaces.py:286-290) mints a synthetic
        membership carrying `role: super_admin` and `via: super_admin`, so
        the crossing is a fact the request holds.
        """
        crossed = repo_module.Repo.for_user(ROOT, BRAVO)
        self.assertEqual(crossed.role(), ws.SUPER_ADMIN)
        self.assertEqual(crossed.membership["via"], "super_admin")
        self.assertEqual([r["id"] for r in crossed.records()], ["bravo-1"])
        self.assertEqual(ws.memberships(ROOT, BRAVO), [])   # no real row

    def test_the_audit_entry_names_the_crossing(self):
        """LEAKED - src/repo.py:168-171.

            def audit(self, action, resource_type=None, resource_id=None, **kw):
                return workspaces.record(self.actor, self.workspace, action,
                                         resource_type, resource_id, **kw)

        `self.membership` is right there and neither the role nor `via`
        reaches the entry. `Repo.for_user`'s own docstring (src/repo.py:
        126-128) promises the opposite: "a super admin included, who gets a
        membership that says `super_admin` so the crossing is named in the
        audit log rather than invisible."

        It is not named. The entry a super admin writes inside B is byte
        identical in shape to one B's own admin writes: same actor field,
        same workspace field, no role, no `via`. Reconstructing "this was
        an outsider" requires joining every entry against the membership
        table and noticing the actor has no row - and that join is
        destroyed the moment somebody is legitimately added to B.

        Nor is there an entry for the crossing itself: the only unscoped
        `workspaces.record` call sites in the web layer are `_refusal`
        (src/web/app.py:559) and `_auth_note` (src/web/app.py:1866), and
        neither fires on a successful workspace entry.
        """
        crossed = repo_module.Repo.for_user(ROOT, BRAVO)
        crossed.audit("campaign.paused", "campaign", "bravo-c1",
                      reason="stopped by hand")

        self.b.audit("campaign.paused", "campaign", "bravo-c1",
                     reason="stopped by hand")

        rows = ws.audit(workspace_slug=BRAVO, action="campaign.paused")
        self.assertEqual(len(rows), 2)
        outsider = next(r for r in rows if r["actor"] == ROOT)
        insider = next(r for r in rows if r["actor"] == BRAVO_OPS)

        # FIXED. `Repo.audit` now carries the membership it is acting under,
        # so the outsider's entry says so and the insider's says what they
        # are. Previously the two were byte-identical apart from the actor,
        # and telling them apart meant joining against the membership table -
        # a join destroyed the moment somebody is legitimately added to B.
        self.assertEqual(outsider["metadata"].get("via"), "super_admin")
        self.assertEqual(outsider["metadata"].get("role"), "super_admin")
        self.assertNotEqual(insider["metadata"].get("via"), "super_admin")
        self.assertNotEqual(
            {k: v for k, v in outsider.items() if k not in ("actor", "at")},
            {k: v for k, v in insider.items() if k not in ("actor", "at")},
            "an outsider's entry is still indistinguishable from a member's")

        # And no entry anywhere records that the crossing happened.
        self.assertEqual(
            [r for r in ws.audit(limit=10000)
             if "super" in str(r.get("action", ""))], [])

    def test_super_admin_is_not_grantable_from_inside_a_workspace(self):
        """BLOCKED - src/workspaces.py:1223 excludes it from
        `assignable_roles`, so no workspace form can mint one."""
        self.assertNotIn(ws.SUPER_ADMIN, ws.assignable_roles())
        with self.assertRaises(ws.RoleNotAssignable):
            ws.invite("new@alpha.test", ALPHA, ws.SUPER_ADMIN)
        with self.assertRaises(ValueError):
            ws.new_membership(ALPHA_OPS, ALPHA, "owner")

    def test_an_invitation_grants_nothing_before_it_is_consumed(self):
        """BLOCKED - src/workspaces.py:291-293 reads memberships only."""
        ws.invite("stranger@nowhere.test", BRAVO, ws.OPERATOR)
        self.assertIsNone(ws.membership_of("stranger@nowhere.test", BRAVO))
        with self.assertRaises(ws.NotAMember):
            repo_module.Repo.for_user("stranger@nowhere.test", BRAVO)


# ----------------------------------------------------------------- attack 12

class SlugsThatDifferByCaseOrByTraversal(Estate):
    """12. `ALPHA`, `../bravo`, and everything else that is not a slug."""

    HOSTILE = ("../bravo", "..\\bravo", "alpha/../bravo", "./bravo",
               "bravo/", "/bravo", "bravo%2F..", "bravo\x00", "bravo ",
               " bravo", "bravo.yaml", "%2e%2e/bravo", "..", ".")

    def test_a_traversal_never_reaches_the_filesystem(self):
        """BLOCKED - src/repo.py:50, `^[a-z0-9][a-z0-9_-]{0,63}$`.

        The grammar refuses dots, slashes, backslashes, NULs, spaces and
        percent signs, so a hostile slug is rejected before `known_clients`
        or any path join is reached.
        """
        for hostile in self.HOSTILE:
            with self.subTest(slug=hostile):
                self.assertFalse(repo_module.valid_slug(hostile))
                with self.assertRaises(repo_module.UnknownClient):
                    repo_module.Repo.for_client(hostile)
                with self.assertRaises(repo_module.UnknownClient):
                    repo_module.Repo(hostile)

    def test_a_traversal_as_a_workspace_slug_is_refused_first(self):
        """BLOCKED - src/repo.py:133-135 checks the slug before it is used
        to look anything up, and raises NotAMember rather than UnknownClient
        so the refusal looks like every other absent workspace."""
        for hostile in self.HOSTILE:
            with self.subTest(slug=hostile):
                with self.assertRaises(ws.NotAMember):
                    repo_module.Repo.for_user(ALPHA_OPS, hostile)

    def test_the_config_loader_refuses_a_traversal_independently(self):
        """BLOCKED - src/clients.py:146-150, a second grammar in front of
        the only path join (`src/clients.py:152`)."""
        for hostile in self.HOSTILE:
            with self.subTest(slug=hostile):
                with self.assertRaises(clients.ConfigError):
                    clients.path_for(hostile)

    def test_case_variants_are_not_slugs(self):
        """BLOCKED - the grammar is lower case only, in both modules.

        This matters more on Windows and macOS than the grammar suggests:
        the filesystem is case-insensitive, so `ALPHA.yaml` and
        `alpha.yaml` are one file. Refusing the mixed-case spelling at the
        top means the case-folding never becomes an aliasing question.
        """
        for variant in ("ALPHA", "Alpha", "aLpHa", "BRAVO"):
            with self.subTest(slug=variant):
                self.assertFalse(repo_module.valid_slug(variant))
                self.assertFalse(clients.valid_slug(variant))
                with self.assertRaises(repo_module.UnknownClient):
                    repo_module.Repo.for_client(variant)
                with self.assertRaises(ws.NotAMember):
                    repo_module.Repo.for_user(ROOT, variant)

    def test_a_mixed_case_config_file_is_not_a_client(self):
        """BLOCKED - src/repo.py:78-80 filters `known_clients` through the
        same grammar, so a file somebody dropped in as `Charlie.yaml` is
        not selectable and cannot shadow anything."""
        with open(os.path.join(os.environ["CLIENTS_DIR"], "Charlie.yaml"),
                  "w", encoding="utf-8") as f:
            f.write(CONFIG.format(slug="charlie", name="Charlie"))
        self.assertEqual(repo_module.known_clients(), [ALPHA, BRAVO])
        with self.assertRaises(repo_module.UnknownClient):
            repo_module.Repo.for_client("Charlie")
        # And the lower-case spelling is not adopted either: the workspace
        # would have to exist, and nothing created one.
        with self.assertRaises(repo_module.UnknownClient):
            repo_module.Repo.for_client("charlie")

    def test_a_mixed_case_workspace_slug_is_dead_on_arrival(self):
        """BLOCKED, though later than it should be.

        `workspaces.ensure` does not validate its slug (src/workspaces.py:
        989-1025), so an `ALPHA` workspace row can be created. Every door
        into it is then shut by `Repo.for_user`'s grammar check, so it
        grants nothing - but it is a row that exists and can never be
        entered, which is worth knowing before somebody debugs it.
        """
        ws.ensure("ALPHA", "Shouty", "ALPHA")
        ws.assign(ROOT, "ALPHA", ws.WORKSPACE_ADMIN)
        self.assertIsNotNone(ws.workspace("ALPHA"))
        with self.assertRaises(ws.NotAMember):
            repo_module.Repo.for_user(ROOT, "ALPHA")

    def test_the_client_a_workspace_names_is_validated_too(self):
        """BLOCKED - src/repo.py:138 hands the workspace's `client` field
        into `Repo.__init__`, which runs the same grammar (src/repo.py:94).

        The field is not user input in the product, but a hand-edited table
        is exactly what `workspaces.ensure` warns about, so it is worth
        knowing the second check is there.
        """
        with ws.transaction() as rows:
            for row in rows:
                if row.get("kind") == "workspace" and row.get("slug") == BRAVO:
                    row["client"] = "../alpha"
        with self.assertRaises(repo_module.UnknownClient):
            repo_module.Repo.for_user(BRAVO_OPS, BRAVO)


if __name__ == "__main__":
    unittest.main()
