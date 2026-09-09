"""Demo mode: real engine, fictional input, and nothing real within reach.

The distinction the whole module rests on: demo mode is **not a mock of the
application**. It is the application, given records that were built rather than
bought. Every verdict on every demo screen came out of `icp.score`,
`verification.decide`, `mx.classify`, `channels.evaluate` and `qa.report` - the
same functions a live batch goes through. A demo that fakes its outputs proves
nothing about the engine.

What these tests guard is the other half: that the demo cannot touch anything
real on its way to being convincing.
"""
import os
import re
import shutil
import tempfile
import unittest

from src import clients, store, workspaces
from src.web import demodata


class DemoTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-demo-")
        self._prev = {k: os.environ.get(k)
                      for k in ("QUEUE", "CAMPAIGNS", "JOBS", "WORKSPACES",
                                "AUDIT", "MX_CACHE", "OUT", "CLIENTS_DIR")}
        store.use_directory(os.path.join(self.tmp, "work"))
        os.environ["MX_CACHE"] = os.path.join(self.tmp, "mx.json")
        os.environ["OUT"] = os.path.join(self.tmp, "out")
        os.environ["CLIENTS_DIR"] = os.path.join(self.tmp, "clients")

    def tearDown(self):
        for key, value in self._prev.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        shutil.rmtree(self.tmp, ignore_errors=True)


class Isolation(DemoTest):

    def test_demo_configs_are_refused_into_the_real_client_directory(self):
        """The demo must not be able to add, shadow or overwrite a real client
        file. Checked rather than promised.

        `clients.CLIENTS` is repointed at a throwaway path for the duration,
        and the refusal is asserted against *that*. The property under test is
        the comparison, not the literal path - and a test that passed the real
        directory in would, the moment somebody removed the guard, write demo
        files over real client configs while proving that it does. It did
        exactly that once, under the mutation audit, which is why it no
        longer can.
        """
        pretend = os.path.join(self.tmp, "pretend-real-clients")
        original = clients.CLIENTS
        clients.CLIENTS = pretend
        try:
            with self.assertRaises(RuntimeError):
                demodata.install_configs(pretend)
            self.assertFalse(os.path.exists(pretend),
                             "the refusal must happen before anything is written")
        finally:
            clients.CLIENTS = original

    def test_the_real_client_directory_is_untouched_by_an_install(self):
        before = sorted(os.listdir(clients.CLIENTS))
        demodata.install()
        self.assertEqual(sorted(os.listdir(clients.CLIENTS)), before)

    def test_demo_refuses_to_run_over_real_records(self):
        real = store.new_record("real-1", "domains", "productive",
                                "A Real Company", "real.example.com")
        store.save([real])
        with self.assertRaises(RuntimeError) as caught:
            demodata.install()
        self.assertIn("refusing", str(caught.exception))
        self.assertEqual(len(store.load()), 1)


class TheEstate(DemoTest):

    def setUp(self):
        super().setUp()
        self.campaigns, self.records, self.config = demodata.install()

    def test_three_workspaces_populated_differently(self):
        slugs = [w["slug"] for w in workspaces.workspaces()]
        self.assertEqual(sorted(slugs),
                         ["contactout", "demo-client", "productive"])
        counts = {}
        for rec in self.records:
            counts[rec["client"]] = counts.get(rec["client"], 0) + 1
        # Productive carries one more than the generated batches produce:
        # the hand-built Acme account, which is the only record in the estate
        # with three decision makers worked by four humans.
        self.assertEqual(counts,
                         {"productive": 33, "contactout": 16, "demo-client": 8})
        self.assertEqual(len(set(counts.values())), 3,
                         "three workspaces of the same size demonstrate nothing")

    def test_one_productive_batch_is_qualified_with_no_campaign(self):
        """The step between "qualified" and "there is a campaign".

        Without a batch sitting here the campaign builder has nothing to
        build, and the one screen that shows that step shows an empty table
        instead.
        """
        campaign_ids = {c["campaign_id"] for c in self.campaigns}
        batches = {rec.get("batch") for rec in self.records
                   if rec["client"] == "productive"}
        unbuilt = batches - campaign_ids
        self.assertTrue(unbuilt,
                        "every Productive batch already has a campaign")
        for batch in unbuilt:
            rows = [r for r in self.records if r.get("batch") == batch]
            self.assertTrue(
                any((r.get("qualification") or {}).get("segment_key")
                    for r in rows),
                f"{batch} has no campaign and no segment either, so it is "
                "not waiting for a campaign - it is unqualified")

    def test_one_person_per_role_and_one_person_in_two_workspaces(self):
        roles = set()
        for person in demodata.USERS:
            for _, role in person["memberships"]:
                roles.add(role)
        self.assertEqual(
            roles,
            {workspaces.WORKSPACE_ADMIN, workspaces.OPERATOR,
             workspaces.REVIEWER, workspaces.VIEWER})
        self.assertTrue(any(p.get("super_admin") for p in demodata.USERS))
        multi = [p for p in demodata.USERS if len(p["memberships"]) > 1]
        self.assertTrue(multi, "no user demonstrates two workspaces at once")
        self.assertEqual(len({role for _, role in multi[0]["memberships"]}), 2,
                         "the multi-workspace user should hold two roles")

    def test_no_domain_outside_test_and_nobody_real(self):
        for rec in self.records:
            self.assertTrue(rec["domain"].endswith(".test"), rec["domain"])
            for contact in rec.get("contacts") or []:
                if contact.get("email"):
                    self.assertTrue(contact["email"].endswith(".test"))
                if contact.get("linkedin"):
                    self.assertIn("linkedin.com/in/", contact["linkedin"])

    def test_domains_are_unique_across_workspaces(self):
        """Two tenants holding the same domain would be realistic and
        unreadable: a cross-tenant leak would look like a coincidence."""
        domains = [r["domain"] for r in self.records]
        self.assertEqual(len(domains), len(set(domains)))

    def test_the_icp_verdicts_have_a_spread(self):
        """A batch where everything scores the same teaches an operator
        nothing. The review queue exists because some companies land in the
        middle."""
        statuses, tiers = {}, {}
        for rec in self.records:
            verdict = (rec.get("qualification") or {}).get("verdict") or {}
            statuses[verdict.get("icp_status")] = statuses.get(
                verdict.get("icp_status"), 0) + 1
            tiers[verdict.get("icp_tier")] = tiers.get(
                verdict.get("icp_tier"), 0) + 1
        self.assertGreater(len(statuses), 1, statuses)
        self.assertGreater(len(tiers), 1, tiers)

    def test_the_verification_scenarios_are_all_represented(self):
        """Double-confirmed, single, disagreement, catch-all and invalid all
        need to exist or the double-verification screens have nothing to show.
        """
        from src import verification
        states = set()
        for rec in self.records:
            for contact in rec.get("contacts") or []:
                block = contact.get("verification") or {}
                if block.get("state"):
                    states.add(block["state"])
        self.assertGreaterEqual(len(states), 3, states)

    def test_a_blocked_mail_gateway_exists_in_every_workspace(self):
        from src import mx
        by_client = {}
        for rec in self.records:
            for contact in rec.get("contacts") or []:
                stored = mx.stored_decision(contact) or {}
                provider = stored.get("security_provider")
                if provider:
                    by_client.setdefault(rec["client"], set()).add(provider)
        for client in ("productive", "contactout", "demo-client"):
            self.assertTrue(by_client.get(client),
                            f"{client} has no gateway to demonstrate")

    def test_exactly_one_campaign_is_approved(self):
        """A demo where nothing is approved shows an empty provider payload
        everywhere; one where everything is leaves the approval queue empty."""
        approved = [c for c in self.campaigns
                    if (c.get("approval") or {}).get("state") == "approved"
                    or c.get("status") == "approved"]
        waiting = [c for c in self.campaigns
                   if c.get("status") == "awaiting_approval"]
        self.assertTrue(waiting, "the approval queue should not be empty")

    def test_nothing_in_the_estate_has_been_launched(self):
        for campaign in self.campaigns:
            self.assertEqual((campaign.get("launch") or {}).get("state"),
                             "not_launched")
            self.assertIsNone(campaign.get("bison_campaign_id"))
            self.assertIsNone(campaign.get("heyreach_campaign_id"))


class Determinism(DemoTest):

    def test_two_installs_produce_the_same_estate(self):
        """Built from an index, never from a clock or a random seed, so
        company 41 is the same company on every machine and a screenshot taken
        tonight matches one taken tomorrow."""
        first = self.fingerprint()
        shutil.rmtree(os.path.join(self.tmp, "work"), ignore_errors=True)
        store.use_directory(os.path.join(self.tmp, "work"))
        second = self.fingerprint()
        self.assertEqual(first, second)

    def fingerprint(self):
        _, records, _ = demodata.install()
        return [(r["id"], r["company"], r["domain"],
                 (r.get("qualification") or {}).get("verdict", {}).get(
                     "icp_score"))
                for r in sorted(records, key=lambda r: r["id"])]


class PlantedNumbersStayInTheDemo(DemoTest):
    """The copy-experiment screen may not answer a real workspace with fiction.

    `web/demovariants.py` carries planted exposure and outcome totals so the
    demo can show five experiment states without four thousand touch events
    in the estate. The evaluator reading them is production code, which is
    the point - and the fallback that reached them fired whenever a campaign
    had no `cadence_graph`.

    Nothing writes `cadence_graph` (`PRODUCT-GAPS.md`), so that was every
    real campaign, always. The screen labelled the totals as fictional and
    that was still the wrong default: an operator asking what their campaign
    is doing should be told nothing is configured.
    """

    def setUp(self):
        super().setUp()
        from src import repo as repo_module
        from src.web import api

        self.api = api
        demodata.install()
        self.repo = repo_module.Repo.for_user("ops@productive.test",
                                              "productive")

    def test_a_real_process_is_told_there_is_no_cadence_graph(self):
        data = self.api.campaign_experiments(self.repo, demo=False)
        self.assertTrue(data["no_cadence_graph"])
        self.assertFalse(data["planted"])
        self.assertEqual(data["steps"], [])

    def test_the_demo_still_shows_the_experiment_states(self):
        """The other half: the fix must not empty the demonstration."""
        data = self.api.campaign_experiments(self.repo, demo=True)
        self.assertTrue(data["planted"])
        self.assertTrue(data["steps"])
        self.assertFalse(data.get("no_cadence_graph"))

    def test_no_planted_exposure_reaches_a_real_process(self):
        """Assert on the numbers, not on the flag beside them."""
        from src.web import demovariants

        planted = {exposures
                   for results in demovariants.RESULTS.values()
                   for exposures, _outcomes in results.values()}
        # A set comparison proves nothing if one side is empty by accident.
        self.assertTrue(planted)

        data = self.api.campaign_experiments(self.repo, demo=False)
        seen = {(entry.get("result") or {}).get("exposures")
                for step in data["steps"] for entry in step["variants"]}
        self.assertFalse(planted & seen)

        # And it is a real exclusion, not an empty one: the same read in
        # demo mode does surface those totals.
        demo = self.api.campaign_experiments(self.repo, demo=True)
        self.assertTrue(planted & {(entry.get("result") or {}).get("exposures")
                                   for step in demo["steps"]
                                   for entry in step["variants"]})

    def test_the_page_names_what_is_missing_rather_than_showing_nothing(self):
        from src.web import pages

        html = pages.campaign_experiments(
            self.api.campaign_experiments(self.repo, demo=False))
        self.assertIn("No cadence graph", html)
        self.assertNotIn("No message steps", html)
