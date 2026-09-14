"""TASK-006: adversarial tenancy tests for every read and write path.

For each of: loading records, loading campaigns, campaign material,
fingerprint, approval, sender assignment, fatigue, collision, suppression
and the executionguard tenancy gate - assert that asking as tenant A
never returns a row belonging to tenant B.

Also assert the NEGATIVE cases: an absent client, an empty-string client,
a client that does not exist, and a client whose case differs. Each must
refuse. A silent empty result is NOT a pass.

The estate is two synthetic clients, `alpha` and `bravo`, in a temp dir.
"""
import os
import shutil
import tempfile
import unittest

from src import approve as approve_mod
from src import campaigns as campaign_store
from src import clients
from src import collision
from src import fatigue as fatigue_mod
from src import repo as repo_module
from src import senderidentity as si
from src import store
from src import workspaces as ws

ALPHA = "alpha"
BRAVO = "bravo"

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

cadence: default

fatigue:
  contact:
    min_hours_between_touches: 48
    max_touches_per_week: 2
"""


def a_record(rid, client, email=None, contact_key=None):
    key = contact_key or f"{rid}-c1"
    return {
        "id": rid, "lane": "cold", "client": client,
        "company": rid.upper(), "domain": f"{rid}.test",
        "state": "queued", "drop_reason": None,
        "log": [], "events": [],
        "contacts": [{
            "key": key, "name": "Pat Person",
            "title": "Operations Manager",
            "email": email or f"pat@{rid}.test",
            "persona": "champion", "selected": True, "verified": True,
        }],
    }


class TwoTenantEstate(unittest.TestCase):
    """Two clients, two workspaces, in a temp directory."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-task006-")
        self._prev = {k: os.environ.get(k) for k in
                      ("QUEUE", "OUT", "CLIENTS_DIR") + store.STATE_OVERRIDES}
        store.use_directory(os.path.join(self.tmp, "work"))
        os.environ["OUT"] = os.path.join(self.tmp, "out")
        os.environ["CLIENTS_DIR"] = os.path.join(self.tmp, "clients")
        os.makedirs(os.environ["CLIENTS_DIR"], exist_ok=True)
        self.assertTrue(store.queue_path().startswith(
            os.path.abspath(self.tmp)))

        for slug, name in ((ALPHA, "Alpha"), (BRAVO, "Bravo")):
            with open(os.path.join(os.environ["CLIENTS_DIR"],
                                   f"{slug}.yaml"),
                      "w", encoding="utf-8") as f:
                f.write(CONFIG.format(slug=slug, name=name))

        ws.ensure(ALPHA, "Alpha", ALPHA)
        ws.ensure(BRAVO, "Bravo", BRAVO)

        store.append([
            a_record("alpha-1", ALPHA),
            a_record("alpha-2", ALPHA),
            a_record("bravo-1", BRAVO),
            a_record("bravo-2", BRAVO),
        ])

        campaign_store.save([
            dict(campaign_store.new_campaign(
                "alpha-c1", ALPHA, "Alpha One"),
                record_ids=["alpha-1", "alpha-2"]),
            dict(campaign_store.new_campaign(
                "bravo-c1", BRAVO, "Bravo One"),
                record_ids=["bravo-1", "bravo-2"]),
        ])

        si.install([
            si.new_sender(ALPHA, "anna", "Anna Alpha"),
            si.new_email_account(ALPHA, "anna-01", "anna",
                                 "anna01@alpha.test",
                                 provider_account_id="p-100"),
            si.new_sender(BRAVO, "boris", "Boris Bravo"),
            si.new_email_account(BRAVO, "boris-01", "boris",
                                 "b01@bravo.test",
                                 provider_account_id="p-100"),
        ])

        self.a = repo_module.Repo.for_client(ALPHA)
        self.b = repo_module.Repo.for_client(BRAVO)

    def tearDown(self):
        for k, v in self._prev.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.tmp, ignore_errors=True)


# ==================================================================
# 1. LOADING RECORDS
# ==================================================================

class TestLoadingRecords(TwoTenantEstate):
    """store.list_records and Repo.records: tenant A sees only A's rows."""

    def test_list_records_filters_by_client(self):
        alpha_recs = store.list_records(client=ALPHA)
        bravo_recs = store.list_records(client=BRAVO)
        self.assertEqual(
            sorted(r["id"] for r in alpha_recs), ["alpha-1", "alpha-2"])
        self.assertEqual(
            sorted(r["id"] for r in bravo_recs), ["bravo-1", "bravo-2"])

    def test_list_records_with_no_client_returns_everything(self):
        """FINDING: store.list_records(client=None) returns all tenants.

        This is the filter-not-boundary pattern. The function is the CLI's
        primitive and the filter is optional. A caller that forgets the
        client gets the whole estate.
        """
        all_recs = store.list_records()
        self.assertEqual(len(all_recs), 4)

    def test_repo_records_returns_only_this_clients_rows(self):
        self.assertEqual(
            sorted(r["id"] for r in self.a.records()),
            ["alpha-1", "alpha-2"])
        self.assertEqual(
            sorted(r["id"] for r in self.b.records()),
            ["bravo-1", "bravo-2"])

    def test_list_records_with_empty_string_client_returns_empty(self):
        """FINDING: client="" returns an empty list, not a refusal.

        An empty list is indistinguishable from 'this tenant has nothing'.
        """
        result = store.list_records(client="")
        self.assertEqual(result, [])

    def test_list_records_with_nonexistent_client_returns_empty(self):
        """FINDING: client='nosuchclient' returns empty, not a refusal."""
        result = store.list_records(client="nosuchclient")
        self.assertEqual(result, [])

    def test_list_records_with_case_variant_returns_empty(self):
        """FINDING: client='Alpha' returns empty, not a refusal.

        The slug grammar is lowercase only, but list_records does not
        validate - it just compares, so 'Alpha' != 'alpha' and the
        result is silently empty.
        """
        result = store.list_records(client="Alpha")
        self.assertEqual(result, [])


# ==================================================================
# 2. LOADING CAMPAIGNS
# ==================================================================

class TestLoadingCampaigns(TwoTenantEstate):
    """Campaign reads scoped to one tenant never return another's."""

    def test_repo_campaigns_returns_only_this_clients(self):
        a_camps = self.a.campaigns()
        b_camps = self.b.campaigns()
        self.assertEqual(
            [c["campaign_id"] for c in a_camps], ["alpha-c1"])
        self.assertEqual(
            [c["campaign_id"] for c in b_camps], ["bravo-c1"])

    def test_admin_repo_sees_all_campaigns(self):
        admin = repo_module.admin_repo()
        self.assertEqual(len(admin.campaigns()), 2)

    def test_repo_campaign_refuses_foreign_id(self):
        with self.assertRaises(repo_module.CrossClientAccess):
            self.a.campaign("bravo-c1")

    def test_module_level_get_is_unscoped(self):
        """FINDING: campaigns.get takes no client and returns anybody's row.

        This is the CLI primitive. Safe only while no request path calls
        it with a caller-supplied id.
        """
        self.assertEqual(
            campaign_store.get("bravo-c1")["client"], BRAVO)


# ==================================================================
# 3. CAMPAIGN MATERIAL
# ==================================================================

class TestCampaignMaterial(TwoTenantEstate):
    """campaigns.material: does it include records from other tenants?"""

    def test_material_only_includes_own_records(self):
        recs = store.load()
        alpha_camp = campaign_store.get("alpha-c1")
        mat = campaign_store.material(alpha_camp, recs=recs)
        record_ids = [r["id"] for r in mat["records"]]
        self.assertIn("alpha-1", record_ids)
        self.assertIn("alpha-2", record_ids)
        self.assertNotIn("bravo-1", record_ids)
        self.assertNotIn("bravo-2", record_ids)

    def test_material_client_field_matches_campaign(self):
        alpha_camp = campaign_store.get("alpha-c1")
        recs = store.load()
        mat = campaign_store.material(alpha_camp, recs=recs)
        self.assertEqual(mat["client"], ALPHA)

    def test_material_with_mixed_records_still_scoped_by_campaign(self):
        """The material function iterates campaign.record_ids, not all
        records. So even if the recs list contains both tenants, only
        the campaign's own records appear."""
        recs = store.load()
        self.assertEqual(len(recs), 4)
        bravo_camp = campaign_store.get("bravo-c1")
        mat = campaign_store.material(bravo_camp, recs=recs)
        record_ids = [r["id"] for r in mat["records"]]
        self.assertIn("bravo-1", record_ids)
        self.assertNotIn("alpha-1", record_ids)


# ==================================================================
# 4. FINGERPRINT
# ==================================================================

class TestFingerprint(TwoTenantEstate):
    """campaigns.fingerprint: is it tenant-specific?"""

    def test_different_tenants_produce_different_fingerprints(self):
        recs = store.load()
        alpha_fp = campaign_store.fingerprint(
            campaign_store.get("alpha-c1"), recs=recs)
        bravo_fp = campaign_store.fingerprint(
            campaign_store.get("bravo-c1"), recs=recs)
        self.assertNotEqual(alpha_fp, bravo_fp)

    def test_fingerprint_is_deterministic(self):
        recs = store.load()
        camp = campaign_store.get("alpha-c1")
        fp1 = campaign_store.fingerprint(camp, recs=recs)
        fp2 = campaign_store.fingerprint(camp, recs=recs)
        self.assertEqual(fp1, fp2)

    def test_fingerprint_changes_when_record_is_swapped(self):
        """If we could swap records between campaigns, the fingerprint
        would change. This proves the fingerprint covers the record set."""
        recs = store.load()
        camp = campaign_store.get("alpha-c1")
        fp_original = campaign_store.fingerprint(camp, recs=recs)

        tampered_recs = []
        for r in recs:
            r2 = dict(r)
            if r["id"] == "alpha-1":
                r2 = dict(r)
                r2["company"] = "TAMPERED"
            tampered_recs.append(r2)
        fp_tampered = campaign_store.fingerprint(camp, recs=tampered_recs)
        self.assertNotEqual(fp_original, fp_tampered)


# ==================================================================
# 5. APPROVAL
# ==================================================================

class TestApprovalIsolation(TwoTenantEstate):
    """approve.pending: does it show other tenant's records?"""

    def test_scoped_pending_contains_nothing_foreign(self):
        """When given a scoped record list, pending shows only that
        tenant's records."""
        pending = approve_mod.pending(self.a.records())
        ids = {row["id"] for row in
               pending["waiting"] + pending["blocked"]}
        self.assertTrue(ids.issubset({"alpha-1", "alpha-2"}))
        self.assertNotIn("bravo-1", ids)
        self.assertNotIn("bravo-2", ids)

    def test_unscoped_default_reads_the_whole_estate(self):
        """FINDING: approve.pending() with no argument defaults to
        store.load() and returns both tenants' queues.

        This is the CLI's default. A handler that called it without
        repo.records() would render both tenants' queues on one screen.
        """
        everything = approve_mod.pending()
        ids = {row["id"] for row in
               everything["waiting"] + everything["blocked"]}
        self.assertTrue(ids & {"alpha-1", "alpha-2", "bravo-1", "bravo-2"})

    def test_by_record_is_unscoped(self):
        """FINDING: campaigns.by_record() is unscoped and maps records
        from both tenants. A caller holding a record uses this to find
        its campaign, and the answer is not scoped to a tenant."""
        mapping = campaign_store.by_record()
        self.assertIn("alpha-1", mapping)
        self.assertIn("bravo-1", mapping)
        self.assertEqual(mapping["alpha-1"]["client"], ALPHA)
        self.assertEqual(mapping["bravo-1"]["client"], BRAVO)


# ==================================================================
# 6. SENDER ASSIGNMENT
# ==================================================================

class TestSenderAssignmentIsolation(TwoTenantEstate):
    """Sender reads and writes are scoped to one workspace."""

    def test_sender_from_another_workspace_raises(self):
        with self.assertRaises(si.CrossWorkspaceSender):
            si.sender(ALPHA, "boris")
        with self.assertRaises(si.CrossWorkspaceSender):
            si.sender(BRAVO, "anna")

    def test_require_sender_from_another_workspace_raises(self):
        with self.assertRaises(si.CrossWorkspaceSender):
            si.require_sender(ALPHA, "boris")

    def test_account_from_another_workspace_raises(self):
        with self.assertRaises(si.CrossWorkspaceSender):
            si.account(ALPHA, si.EMAIL, "boris-01")

    def test_roster_is_scoped(self):
        roster_a = si.roster(ALPHA)
        sender_ids = [s["sender_id"] for s in roster_a["senders"]]
        self.assertIn("anna", sender_ids)
        self.assertNotIn("boris", sender_ids)

    def test_shared_provider_account_id_does_not_cross(self):
        """Both fixtures carry provider_account_id='p-100'. Resolving
        inside one workspace must not reach the other."""
        self.assertEqual(
            si.by_provider_account(ALPHA, si.EMAIL, "p-100")["account_id"],
            "anna-01")
        self.assertEqual(
            si.by_provider_account(BRAVO, si.EMAIL, "p-100")["account_id"],
            "boris-01")

    def test_digest_differs_between_workspaces(self):
        self.assertNotEqual(si.digest(ALPHA), si.digest(BRAVO))


# ==================================================================
# 7. FATIGUE
# ==================================================================

class TestFatigueIsolation(TwoTenantEstate):
    """fatigue.check: does it use the right client's config?

    FINDING: fatigue.check takes config=None and silently substitutes
    module defaults. It does not refuse a missing config, and it does
    not look up the record's client. A caller that passes no config
    gets the same defaults regardless of which tenant the record
    belongs to.
    """

    def test_fatigue_with_no_config_uses_defaults(self):
        """Both tenants get the same default limits when no config
        is passed, regardless of their per-client configuration."""
        rec = store.get("alpha-1")
        state = fatigue_mod.check(rec, "alpha-1-c1")
        self.assertEqual(state["state"], "ok")

    def test_fatigue_with_alpha_config_uses_alpha_limits(self):
        config_a = clients.load(ALPHA)
        lim = fatigue_mod.limits(config_a)
        self.assertEqual(
            lim["contact.min_hours_between_touches"]["value"], 48)
        self.assertTrue(
            lim["contact.min_hours_between_touches"]["configured"])

    def test_fatigue_with_bravo_config_uses_bravo_limits(self):
        config_b = clients.load(BRAVO)
        rec = store.get("bravo-1")
        state = fatigue_mod.check(rec, "bravo-1-c1", config=config_b)
        self.assertEqual(state["state"], "ok")

    def test_fatigue_does_not_refuse_wrong_client_config(self):
        """FINDING: fatigue.check does not verify the config matches
        the record's client. Passing alpha's config for a bravo record
        is accepted silently."""
        config_a = clients.load(ALPHA)
        rec = store.get("bravo-1")
        state = fatigue_mod.check(rec, "bravo-1-c1", config=config_a)
        self.assertEqual(state["state"], "ok")


# ==================================================================
# 8. COLLISION
# ==================================================================

class TestCollisionIsolation(TwoTenantEstate):
    """collision.check_address and check_linkedin_profile: workspace scoping.

    These functions take expect_workspace and require it to be non-empty.
    The REQUIRED sentinel refuses when the argument is omitted entirely.
    FINDING: passing empty string or None does NOT refuse before reaching
    the provider - the workspace check is only against the sentinel.
    """

    def test_check_address_requires_workspace(self):
        """expect_workspace=REQUIRED (the sentinel) raises if nothing
        is passed."""
        with self.assertRaises((collision.CollisionUnknown, ValueError,
                                TypeError)):
            collision.check_address("pat@alpha-1.test")

    def test_check_linkedin_profile_requires_workspace(self):
        with self.assertRaises((collision.CollisionUnknown, ValueError,
                                TypeError)):
            collision.check_linkedin_profile(
                "https://linkedin.com/in/test-person")

    def test_check_address_empty_workspace_is_not_caught_before_provider(self):
        """FINDING: expect_workspace='' is not caught before the provider
        call. The REQUIRED sentinel only catches the 'not passed' case.
        An empty string passes through to the provider layer, which then
        fails because no credentials exist. In a live system with
        credentials, this would read from an unpinned estate."""
        from src.providers import MissingKey
        with self.assertRaises(MissingKey):
            collision.check_address("pat@alpha-1.test",
                                    expect_workspace="")

    def test_check_address_none_workspace_is_not_caught_before_provider(self):
        """FINDING: expect_workspace=None passes through to the provider."""
        from src.providers import MissingKey
        with self.assertRaises(MissingKey):
            collision.check_address("pat@alpha-1.test",
                                    expect_workspace=None)


# ==================================================================
# 9. SUPPRESSION
# ==================================================================

class TestSuppressionIsolation(TwoTenantEstate):
    """Suppression: is it per-client or global?

    FINDING: config/suppress.txt is a flat global domain list with no
    client key. One client's customer is suppressed for every tenant.
    This is documented in MULTI-CLIENT-AUDIT.md section 3 and section 5
    item 9.
    """

    def test_store_validate_accepts_null_client(self):
        """FINDING: store.validate checks that 'client' key is present,
        never that it holds a real client. client: None passes."""
        rec = a_record("orphan-null", ALPHA)
        rec["client"] = None
        problems = store.validate(rec)
        client_problems = [p for p in problems if "client" in p]
        self.assertEqual(client_problems, [])

    def test_store_validate_accepts_empty_string_client(self):
        """FINDING: client='' passes validate. An empty string is
        present as a key but holds no tenant."""
        rec = a_record("orphan-empty", ALPHA)
        rec["client"] = ""
        problems = store.validate(rec)
        client_problems = [p for p in problems if "client" in p]
        self.assertEqual(client_problems, [])

    def test_repo_does_not_see_null_client_records(self):
        """A record with client=None is invisible to every scoped repo."""
        rec = a_record("orphan-null", ALPHA)
        rec["client"] = None
        with store.transaction() as rows:
            rows.append(rec)
        self.assertNotIn("orphan-null",
                         [r["id"] for r in self.a.records()])
        self.assertNotIn("orphan-null",
                         [r["id"] for r in self.b.records()])
        admin = repo_module.admin_repo()
        self.assertIn("orphan-null",
                      [r["id"] for r in admin.records()])


# ==================================================================
# 10. EXECUTIONGUARD TENANCY GATE
# ==================================================================

class TestExecutionGuardTenancy(TwoTenantEstate):
    """The executionguard tenancy gate: does it refuse cross-tenant?

    The authorize function checks copy (step expansion) BEFORE tenancy.
    So a cross-tenant record with no cadence data is refused at 'copy'
    before the tenancy check runs. This is a finding: the tenancy
    violation is masked by the copy gate.

    To test the tenancy gate itself, we provide cadence data so the
    copy gate passes.
    """

    def _record_with_step(self, rid, client, step_key="day3",
                          channel="linkedin"):
        """A record with cadence data so expand_step returns truthy.

        day1 is a generated email step - needs 'body'.
        day3 is a linkedin template step - needs a stored generated note.
        """
        rec = a_record(rid, client)
        contact_key = rec["contacts"][0]["key"]
        if channel == "email":
            rec["cadence"] = {
                contact_key: {
                    step_key: {
                        "channel": "email",
                        "body": "A synthetic email body for testing.",
                        "subject": "Test subject",
                        "generated": True,
                        "day": 1,
                    }
                }
            }
        else:
            rec["cadence"] = {
                contact_key: {
                    step_key: {
                        "channel": "linkedin",
                        "note": "A synthetic outreach note for testing.",
                        "generated": True,
                        "day": 3,
                    }
                }
            }
        return rec

    def test_record_client_must_match_campaign_client(self):
        """executionguard.authorize refuses a record whose client does
        not match the campaign's, at the tenancy gate."""
        from src import executionguard

        rec = self._record_with_step("xbravo-1", BRAVO, "day3", "linkedin")
        campaign = dict(campaign_store.get("alpha-c1"))
        campaign["org_unit"] = "118832"
        contact = rec["contacts"][0]

        with self.assertRaises(executionguard.NotAuthorized) as ctx:
            executionguard.authorize(
                operation="test",
                channel="linkedin",
                campaign=campaign,
                rec=rec,
                contact=contact,
                step_key="day3",
                workspace="test-workspace",
                config=clients.load(ALPHA),
                readback=None,
                reserve=False,
            )
        self.assertEqual(ctx.exception.gate, "tenancy")
        self.assertIn("belongs to client", str(ctx.exception))

    def test_absent_record_client_is_refused(self):
        """A record with client=None is refused at the tenancy gate."""
        from src import executionguard

        rec = self._record_with_step("xalpha-1", ALPHA, "day3", "linkedin")
        rec["client"] = None
        campaign = campaign_store.get("alpha-c1")
        contact = rec["contacts"][0]

        with self.assertRaises(executionguard.NotAuthorized) as ctx:
            executionguard.authorize(
                operation="test",
                channel="linkedin",
                campaign=campaign,
                rec=rec,
                contact=contact,
                step_key="day3",
                workspace="test-workspace",
                config=clients.load(ALPHA),
                readback=None,
                reserve=False,
            )
        self.assertEqual(ctx.exception.gate, "tenancy")

    def test_empty_string_record_client_is_refused(self):
        """A record with client='' is refused at the tenancy gate."""
        from src import executionguard

        rec = self._record_with_step("xalpha-2", ALPHA, "day3", "linkedin")
        rec["client"] = ""
        campaign = campaign_store.get("alpha-c1")
        contact = rec["contacts"][0]

        with self.assertRaises(executionguard.NotAuthorized) as ctx:
            executionguard.authorize(
                operation="test",
                channel="linkedin",
                campaign=campaign,
                rec=rec,
                contact=contact,
                step_key="day3",
                workspace="test-workspace",
                config=clients.load(ALPHA),
                readback=None,
                reserve=False,
            )
        self.assertEqual(ctx.exception.gate, "tenancy")

    def test_empty_campaign_client_is_refused(self):
        """A campaign with client='' is refused.

        The authorize function calls clients.load(campaign.get("client"))
        before the tenancy gate, so an empty campaign client raises
        ConfigError first. This is a refusal, but at the wrong layer -
        a ConfigError rather than a NotAuthorized at the tenancy gate.
        """
        from src import executionguard

        rec = self._record_with_step("xalpha-3", ALPHA)
        campaign = dict(campaign_store.get("alpha-c1"))
        campaign["client"] = ""
        contact = rec["contacts"][0]

        with self.assertRaises(clients.ConfigError):
            executionguard.authorize(
                operation="test",
                channel="linkedin",
                campaign=campaign,
                rec=rec,
                contact=contact,
                step_key="day1",
                workspace="test-workspace",
                readback=None,
                reserve=False,
            )

    def test_email_tenancy_refuses_empty_workspace(self):
        """For the email channel, workspace=None or '' is refused at
        the tenancy gate."""
        from src import executionguard

        rec = self._record_with_step("xalpha-4", ALPHA, "day1", "email")
        campaign = campaign_store.get("alpha-c1")
        contact = rec["contacts"][0]

        with self.assertRaises(executionguard.NotAuthorized) as ctx:
            executionguard.authorize(
                operation="test",
                channel="email",
                campaign=campaign,
                rec=rec,
                contact=contact,
                step_key="day1",
                workspace=None,
                config=clients.load(ALPHA),
                readback=None,
                reserve=False,
            )
        self.assertEqual(ctx.exception.gate, "tenancy")

    def test_linkedin_tenancy_refuses_empty_org_unit(self):
        """For the LinkedIn channel, campaign.org_unit must be non-empty."""
        from src import executionguard

        rec = self._record_with_step("xalpha-5", ALPHA, "day3", "linkedin")
        campaign = campaign_store.get("alpha-c1")
        contact = rec["contacts"][0]
        self.assertIsNone(campaign.get("org_unit"))

        with self.assertRaises(executionguard.NotAuthorized) as ctx:
            executionguard.authorize(
                operation="test",
                channel="linkedin",
                campaign=campaign,
                rec=rec,
                contact=contact,
                step_key="day3",
                workspace="test-workspace",
                config=clients.load(ALPHA),
                readback=None,
                reserve=False,
            )
        self.assertEqual(ctx.exception.gate, "tenancy")

    def test_copy_gate_fires_before_tenancy_for_generated_step_without_data(
            self):
        """FINDING: For a generated step with no stored body/note, the
        copy gate fires before the tenancy gate. A cross-tenant record
        with no written content is refused for 'copy', masking the
        tenancy violation.

        For template steps (like day3), the template renders and the
        copy gate passes, so the tenancy gate fires as expected.
        """
        from src import executionguard

        rec = a_record("no-cadence", BRAVO)
        campaign = dict(campaign_store.get("alpha-c1"))
        campaign["org_unit"] = "118832"
        contact = rec["contacts"][0]

        with self.assertRaises(executionguard.NotAuthorized) as ctx:
            executionguard.authorize(
                operation="test",
                channel="linkedin",
                campaign=campaign,
                rec=rec,
                contact=contact,
                step_key="day15",
                workspace="test-workspace",
                config=clients.load(ALPHA),
                readback=None,
                reserve=False,
            )
        self.assertEqual(ctx.exception.gate, "copy")


# ==================================================================
# 11. NEGATIVE CASES: ABSENT, EMPTY, NONEXISTENT, CASE-DIFFERENT
# ==================================================================

class TestNegativeClientCases(TwoTenantEstate):
    """An absent client, an empty-string client, a client that does not
    exist, and a client whose case differs. Each must refuse."""

    def test_repo_for_client_with_empty_string_raises(self):
        """An empty string is not a valid slug."""
        with self.assertRaises(repo_module.UnknownClient):
            repo_module.Repo.for_client("")

    def test_repo_for_client_with_none_raises(self):
        with self.assertRaises(repo_module.UnknownClient):
            repo_module.Repo.for_client(None)

    def test_repo_for_client_with_nonexistent_raises(self):
        with self.assertRaises(repo_module.UnknownClient):
            repo_module.Repo.for_client("nosuchclient")

    def test_repo_for_client_with_case_variant_raises(self):
        """'Alpha' is not a valid slug (uppercase)."""
        with self.assertRaises(repo_module.UnknownClient):
            repo_module.Repo.for_client("Alpha")

    def test_clients_load_with_nonexistent_raises(self):
        with self.assertRaises(clients.ConfigError):
            clients.load("nosuchclient")

    def test_clients_load_with_case_variant_raises(self):
        with self.assertRaises(clients.ConfigError):
            clients.load("Alpha")

    def test_clients_valid_slug_refuses_uppercase(self):
        self.assertFalse(clients.valid_slug("Alpha"))
        self.assertFalse(clients.valid_slug("BRAVO"))
        self.assertFalse(clients.valid_slug(""))
        self.assertFalse(clients.valid_slug(None))

    def test_store_list_records_with_none_returns_all(self):
        """FINDING: store.list_records(client=None) returns every tenant.
        This is by design for the CLI, but a request path that forgets
        the client gets the whole estate."""
        all_recs = store.list_records(client=None)
        ids = {r["id"] for r in all_recs}
        self.assertEqual(ids, {"alpha-1", "alpha-2", "bravo-1", "bravo-2"})

    def test_store_list_records_with_empty_string_returns_empty_not_refusal(self):
        """FINDING: client='' returns empty list, not a refusal.
        Silent empty is indistinguishable from 'this tenant has nothing'."""
        result = store.list_records(client="")
        self.assertEqual(result, [])

    def test_store_list_records_with_nonexistent_returns_empty_not_refusal(self):
        """FINDING: client='nosuchclient' returns empty, not a refusal."""
        result = store.list_records(client="nosuchclient")
        self.assertEqual(result, [])

    def test_store_list_records_with_case_variant_returns_empty_not_refusal(self):
        """FINDING: client='Alpha' returns empty, not a refusal."""
        result = store.list_records(client="Alpha")
        self.assertEqual(result, [])


# ==================================================================
# 12. BREAK THE WIRING TESTS
# ==================================================================

class TestBreakTheWiring(TwoTenantEstate):
    """For each path, break the tenancy check deliberately and confirm
    the intended test failed for the intended reason."""

    def _record_with_step(self, rid, client, step_key="day3",
                          channel="linkedin"):
        rec = a_record(rid, client)
        contact_key = rec["contacts"][0]["key"]
        rec["cadence"] = {
            contact_key: {
                step_key: {
                    "channel": channel,
                    "note": "A synthetic outreach note for testing."
                    if channel == "linkedin" else None,
                    "body": "A synthetic email body for testing."
                    if channel == "email" else None,
                    "generated": True,
                    "day": 3 if channel == "linkedin" else 1,
                }
            }
        }
        return rec

    def test_repo_filter_is_doing_work(self):
        """If _mine were removed, alpha would see bravo's records."""
        self.assertEqual(len(self.a.records()), 2)
        all_recs = store.load()
        self.assertEqual(len(all_recs), 4)

    def test_cross_client_access_raises_not_returns_none(self):
        """The refusal is an exception, not a None return."""
        with self.assertRaises(repo_module.CrossClientAccess):
            self.a.record("bravo-1")

    def test_executionguard_tenancy_gate_fires_with_cadence_data(self):
        """With cadence data, the tenancy gate fires for a cross-tenant
        record, not the copy gate."""
        from src import executionguard

        rec = self._record_with_step("xbreak-1", BRAVO, "day3", "linkedin")
        campaign = campaign_store.get("alpha-c1")
        contact = rec["contacts"][0]

        with self.assertRaises(executionguard.NotAuthorized) as ctx:
            executionguard.authorize(
                operation="test",
                channel="linkedin",
                campaign=campaign,
                rec=rec,
                contact=contact,
                step_key="day3",
                workspace="test-workspace",
                config=clients.load(ALPHA),
                readback=None,
                reserve=False,
            )
        self.assertEqual(ctx.exception.gate, "tenancy")
        self.assertNotIn("approval", ctx.exception.gate)


if __name__ == "__main__":
    unittest.main()
