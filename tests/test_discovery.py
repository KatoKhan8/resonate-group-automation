"""What is genuinely new, and nothing else.

Four properties, and every test is one of them:

**A known company is never proposed as new.** A discovery run that returns
the client's own customers is worse than one that returns nothing. Nothing
costs nothing; a padded list costs their trust, the first time they read
it.

**What could not be checked is named.** The CRM is not connected. A delta
computed without it is not a smaller delta, it is a wrong one, and the
screen has to be able to say which it is looking at.

**Provenance is mandatory.** A candidate carries the source that proposed
it and evidence a person could argue with. One that cannot be questioned
cannot be rejected, which is how a bad list gets approved.

**It spends nothing.** Discovery proposes; enrichment costs money and
happens after a human approves.
"""
import os
import shutil
import tempfile
import unittest

from src import (campaigns as campaign_store, discovery, ingest,
                 repo as repo_module, store, workspaces)
from tests.base import ProviderTest

WS = "productive"


class DiscoveryTest(ProviderTest):

    def setUp(self):
        super().setUp()
        self.tmp = tempfile.mkdtemp(prefix="rga-disc-")
        self._env = {k: os.environ.get(k) for k in
                     ("QUEUE", "CAMPAIGNS", "JOBS", "WORKSPACES", "AUDIT",
                      "DISCOVERY", "SUPPRESS", "CLIENTS_DIR", "OUT")}
        store.use_directory(os.path.join(self.tmp, "work"))
        os.environ["CLIENTS_DIR"] = os.path.join(self.tmp, "clients")
        os.environ["OUT"] = os.path.join(self.tmp, "out")

        from src.web import demodata
        demodata.install_configs()
        workspaces.ensure(WS, "Productive", client="productive")
        workspaces.ensure("contactout", "ContactOut", client="contactout")
        workspaces.add_user("op@x.test", "Op")
        workspaces.assign("op@x.test", WS, workspaces.OPERATOR)

    def tearDown(self):
        for key, value in self._env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        shutil.rmtree(self.tmp, ignore_errors=True)
        super().tearDown()

    def repo(self, workspace=WS):
        return repo_module.Repo.for_user("op@x.test", workspace)

    def seed(self, *domains, client="productive"):
        rows = []
        for domain in domains:
            rows.append(store.new_record(
                ingest.slug(domain), "domains", client,
                domain.split(".")[0].title(), domain))
        store.save(store.load() + rows)
        return rows

    def propose(self, *domains, **kw):
        kw.setdefault("evidence", "digital agency, Berlin, 60 staff listed")
        return [discovery.candidate(WS, d, run="r1", **kw) for d in domains]

    def universe(self, seen=()):
        return discovery.known(self.repo(), seen=seen)


class AKnownCompanyIsNeverNew(DiscoveryTest):

    def test_a_company_already_in_the_workspace_is_excluded(self):
        self.seed("known-test.example")
        out = discovery.delta(self.propose("known-test.example",
                                           "fresh-test.example"),
                              self.universe())
        self.assertEqual([r["domain"] for r in out["new"]],
                         ["fresh-test.example"])
        self.assertEqual(out["counts"][discovery.KNOWN_RECORD], 1)

    def test_a_company_already_in_a_campaign_says_so_rather_than_known(self):
        """Both are true and one is more useful."""
        self.seed("incamp-test.example")
        campaign_store.save([{
            "campaign_id": "c1", "name": "C", "client": "productive",
            "status": "draft",
            "record_ids": [ingest.slug("incamp-test.example")]}])
        out = discovery.delta(self.propose("incamp-test.example"),
                              self.universe())
        self.assertEqual(out["excluded"][0]["verdict"], discovery.IN_CAMPAIGN)

    def test_a_suppressed_company_is_excluded_and_outranks_everything(self):
        """Suppression is checked before "we already have them": both are
        true, and the operator needs the one that settles it."""
        self.seed("stop-test.example")
        universe = discovery.known(self.repo(),
                                   suppressed={"stop-test.example"})
        out = discovery.delta(self.propose("stop-test.example"), universe)
        self.assertEqual(out["excluded"][0]["verdict"], discovery.SUPPRESSED)

    def test_the_caller_can_supply_the_suppression_set(self):
        """So a weekly run reads that file once rather than once per
        workspace."""
        universe = discovery.known(self.repo(), suppressed={"a-test.example"})
        self.assertIn("a-test.example", universe["suppressed"])

    def test_a_company_an_earlier_run_proposed_is_not_new_again(self):
        out = discovery.delta(self.propose("again-test.example"),
                              self.universe(seen=["again-test.example"]))
        self.assertEqual(out["new"], [])
        self.assertEqual(out["excluded"][0]["verdict"], discovery.SEEN_BEFORE)

    def test_a_company_the_client_ruled_on_is_not_proposed_again(self):
        out = discovery.delta(
            self.propose("ruled-test.example"), self.universe(),
            decided={"ruled-test.example": "existing_client"})
        self.assertEqual(out["new"], [])
        self.assertIn("existing_client", out["excluded"][0]["why"])

    def test_the_same_domain_twice_in_one_run_is_one_candidate(self):
        """A source that lists a company twice has not found it twice."""
        out = discovery.delta(
            self.propose("dup-test.example", "dup-test.example"),
            self.universe())
        self.assertEqual(len(out["new"]), 1)

    def test_identity_is_the_normalised_domain(self):
        self.seed("case-test.example")
        out = discovery.delta(
            [discovery.candidate(WS, "HTTPS://WWW.Case-Test.Example/careers",
                                 evidence="agency, 40 staff listed")],
            self.universe())
        self.assertEqual(out["new"], [])

    def test_a_similar_name_is_not_a_match(self):
        """No fuzzy company-name matching. Two names that look alike may be
        one company or two competitors, and the cost of being wrong is not
        symmetric."""
        self.seed("acme-test.example")
        out = discovery.delta(self.propose("acme-limited-test.example"),
                              self.universe())
        self.assertEqual(len(out["new"]), 1)


class WhatCouldNotBeCheckedIsNamed(DiscoveryTest):

    def test_the_missing_crm_is_reported_on_every_delta(self):
        out = discovery.delta(self.propose("x-test.example"), self.universe())
        sources = [row["source"] for row in out["unavailable"]]
        self.assertIn("crm", sources)

    def test_the_crm_gap_carries_a_live_marker(self):
        out = self.universe()
        crm = [r for r in out["unavailable"] if r["source"] == "crm"][0]
        self.assertEqual(crm["marker"], "LIVE CRM CONNECTOR REQUIRED")

    def test_agency_dnc_is_named_as_not_applicable_here(self):
        """It is person-level and a candidate is a domain with nobody on
        it. "We did not check" and "there was nothing to check" are
        different sentences."""
        out = self.universe()
        sources = [row["source"] for row in out["unavailable"]]
        self.assertIn("agency_dnc", sources)

    def test_no_verdict_claims_an_agency_check_that_cannot_happen(self):
        self.assertNotIn("agency_suppressed", discovery.VERDICTS)

    def test_every_verdict_has_a_label(self):
        self.assertEqual(set(discovery.VERDICTS),
                         set(discovery.VERDICT_LABEL))

    def test_the_delta_says_what_it_was_checked_against(self):
        self.seed("a-test.example", "b-test.example")
        out = discovery.delta(self.propose("c-test.example"), self.universe())
        self.assertEqual(out["checked_against"]["records"], 2)


class ProvenanceIsMandatory(DiscoveryTest):

    def test_a_candidate_without_evidence_is_refused(self):
        with self.assertRaises(discovery.DiscoveryRefused):
            discovery.candidate(WS, "x-test.example", evidence="")

    def test_thin_evidence_is_refused_with_an_example(self):
        with self.assertRaises(discovery.DiscoveryRefused) as caught:
            discovery.candidate(WS, "x-test.example", evidence="matched")
        self.assertIn("Berlin", str(caught.exception))

    def test_an_unusable_domain_is_refused(self):
        with self.assertRaises(discovery.DiscoveryRefused):
            discovery.candidate(WS, "not a domain",
                                evidence="agency, 40 staff listed")

    def test_an_unknown_source_is_refused(self):
        with self.assertRaises(discovery.DiscoveryRefused):
            discovery.candidate(WS, "x-test.example", source="vibes",
                                evidence="agency, 40 staff listed")

    def test_the_source_travels_with_the_candidate(self):
        entry = discovery.candidate(
            WS, "x-test.example", source=discovery.MANUAL,
            found_by="ops@productive.test",
            evidence="agency, 40 staff listed on their site")
        self.assertEqual(entry["source"], discovery.MANUAL)
        self.assertEqual(entry["found_by"], "ops@productive.test")

    def test_facts_from_a_source_are_not_a_verdict(self):
        """A discovery source has no standing to decide ICP."""
        entry = discovery.candidate(
            WS, "x-test.example", evidence="agency, 40 staff listed",
            facts={"employees": 40})
        self.assertNotIn("icp_status", entry)
        self.assertEqual(entry["facts"]["employees"], 40)


class DiscoveryIsScopedToOneWorkspace(DiscoveryTest):

    def test_another_workspaces_records_are_not_in_the_universe(self):
        self.seed("theirs-test.example", client="contactout")
        out = discovery.delta(self.propose("theirs-test.example"),
                              self.universe())
        self.assertEqual(len(out["new"]), 1)

    def test_stored_runs_are_filtered_by_workspace(self):
        discovery.record(self.propose("mine-test.example"))
        discovery.record([discovery.candidate(
            "contactout", "theirs-test.example",
            evidence="agency, 40 staff listed")])
        self.assertEqual(discovery.domains_seen(WS), {"mine-test.example"})

    def test_a_candidate_must_name_its_workspace(self):
        entry = discovery.candidate(WS, "x-test.example",
                                    evidence="agency, 40 staff listed")
        entry["workspace"] = None
        with self.assertRaises(discovery.DiscoveryRefused):
            discovery.record([entry])


class RunsAreAppendOnly(DiscoveryTest):

    def test_a_second_run_does_not_erase_the_first(self):
        discovery.record(self.propose("one-test.example"))
        discovery.record(self.propose("two-test.example"))
        self.assertEqual(len(discovery.load(WS)), 2)

    def test_what_was_proposed_before_is_answerable(self):
        """The whole question the module exists to answer."""
        discovery.record(self.propose("one-test.example"))
        self.assertIn("one-test.example", discovery.domains_seen(WS))

    def test_runs_are_grouped_and_dated(self):
        discovery.record(self.propose("one-test.example",
                                      "two-test.example"))
        found = discovery.runs(WS)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["candidates"], 2)
        self.assertTrue(found[0]["at"])


class DiscoverySpendsNothing(DiscoveryTest):

    def test_building_the_universe_calls_no_provider(self):
        self.seed("a-test.example")
        self.universe()
        self.assertEqual(self.cassette.calls, [])

    def test_a_whole_delta_calls_no_provider(self):
        self.seed("a-test.example")
        discovery.delta(self.propose("b-test.example"), self.universe())
        self.assertEqual(self.cassette.calls, [])

    def test_the_delta_reports_that_it_spent_nothing(self):
        out = discovery.delta(self.propose("b-test.example"),
                              self.universe())
        self.assertEqual(out["spent"], 0)

    def test_recording_candidates_calls_no_provider(self):
        discovery.record(self.propose("b-test.example"))
        self.assertEqual(self.cassette.calls, [])



class ScreenTest(DiscoveryTest):
    """A recorded run to read.

    The screen reads the discovery store rather than a fixture module,
    so the fixture has to write to that store like anything else would.
    """

    def setUp(self):
        super().setUp()
        self.seed("known-test.example")
        discovery.record([
            discovery.candidate(
                WS, "old-test.example", run="2026-01-01",
                evidence="proposed by an earlier run entirely"),
        ])
        discovery.record([
            discovery.candidate(
                WS, domain, run="2026-02-01", source=discovery.PROVIDER,
                evidence="digital agency, Berlin, 60 staff listed")
            for domain in ("fresh-one.example", "fresh-two.example",
                           "known-test.example", "old-test.example")])


class TheDiscoveryScreen(ScreenTest):
    """The delta, reachable. The engine existed before anything could get
    to it, which made it code rather than a product."""

    def view(self, email="op@x.test"):
        from src.web import api
        return api.discovery_view(
            repo_module.Repo.for_user(email, WS))

    def test_it_reports_what_was_proposed_and_what_survived(self):
        found = self.view()
        self.assertEqual(found["counts"]["proposed"],
                         found["counts"]["new"]
                         + found["counts"]["already_known"])

    def test_it_spends_nothing(self):
        self.view()
        self.assertEqual(self.cassette.calls, [])
        self.assertEqual(self.view()["spent"], 0)

    def test_a_run_with_nothing_excluded_still_shows_its_result(self):
        """A precedence bug swallowed the whole screen above an
        unparenthesised ternary: with no excluded rows the counts and the
        "nothing new" note vanished, and the page rendered without its own
        answer on it."""
        from src.web import pages

        html = pages.discovery_view({
            "new": [], "excluded": [],
            "unavailable": [{"source": "crm", "why": "not connected",
                             "marker": "LIVE CRM CONNECTOR REQUIRED"}],
            "counts": {"proposed": 0, "new": 0, "already_known": 0},
            "spent": 0, "review_rows": 0, "can_export": True})

        self.assertIn("Nothing new this run", html)
        self.assertIn("could not be checked", html)
        self.assertIn("proposed", html)

    def test_a_run_with_exclusions_shows_both_halves(self):
        from src.web import pages

        html = pages.discovery_view({
            "new": [{"domain": "a.test", "company": "A",
                     "evidence": "agency, 40 staff", "source": "provider"}],
            "excluded": [{"domain": "b.test", "company": "B",
                          "verdict": "known_record", "why": "already here"}],
            "unavailable": [],
            "counts": {"proposed": 2, "new": 1, "already_known": 1},
            "spent": 0, "review_rows": 1, "can_export": True})

        self.assertIn("Proposed and already known", html)
        self.assertNotIn("Nothing new this run", html)

    def test_it_names_what_could_not_be_checked(self):
        sources = [row["source"] for row in self.view()["unavailable"]]
        self.assertIn("crm", sources)

    def test_a_reviewer_may_read_it(self):
        workspaces.add_user("rev@x.test", "Rev")
        workspaces.assign("rev@x.test", WS, workspaces.REVIEWER)
        self.assertIsNotNone(self.view("rev@x.test"))

    def test_a_viewer_may_not(self):
        """Discovery is agency working state, not a client outcome."""
        workspaces.add_user("view@x.test", "View")
        workspaces.assign("view@x.test", WS, workspaces.VIEWER)
        with self.assertRaises(workspaces.NotPermitted):
            self.view("view@x.test")


class TheReviewExport(ScreenTest):

    def export(self, email="op@x.test"):
        from src.web import api
        return api.discovery_csv(repo_module.Repo.for_user(email, WS))

    def test_it_is_named_for_the_run_the_candidates_belong_to(self):
        """The batch is part of the candidate id. A file named for the
        wrong run produces ids that fail to match on return, and every
        row is refused as one we never sent."""
        from src.web import api
        from src import clientreview

        found = self.export()
        view = api.discovery_view(repo_module.Repo.for_user("op@x.test", WS))
        sent = clientreview.fingerprint(WS, found["batch"], view["new"])

        first = found["csv"].strip().splitlines()[1].split(",")[0]
        self.assertIn(first, sent)

    def test_the_row_count_matches_the_new_candidates(self):
        from src.web import api
        view = api.discovery_view(repo_module.Repo.for_user("op@x.test", WS))
        self.assertEqual(self.export()["rows"], len(view["new"]))

    def test_only_new_candidates_are_exported(self):
        """A client should never be asked about a company they already
        ruled on.

        Compared on the id rather than the domain: a domain can be both
        new and excluded in one run, because a source that lists a company
        twice produces one candidate and one duplicate row.
        """
        from src.web import api
        from src import clientreview

        repo = repo_module.Repo.for_user("op@x.test", WS)
        view = api.discovery_view(repo)
        found = self.export()
        exported = {line.split(",")[0]
                    for line in found["csv"].strip().splitlines()[1:]}
        new_ids = {clientreview.candidate_id(WS, found["batch"], row["domain"])
                   for row in view["new"]}
        self.assertEqual(exported, new_ids)

        settled = {row["domain"] for row in view["excluded"]
                   if row["verdict"] != discovery.SEEN_BEFORE}
        for domain in settled:
            self.assertNotIn(
                clientreview.candidate_id(WS, found["batch"], domain),
                exported)

    def test_a_role_without_export_cannot_download_it(self):
        """Contact-adjacent data leaving the building is governed by the
        permission that already governs data leaving."""
        workspaces.add_user("rev2@x.test", "Rev")
        workspaces.assign("rev2@x.test", WS, workspaces.REVIEWER)
        with self.assertRaises(workspaces.NotPermitted):
            self.export("rev2@x.test")


if __name__ == "__main__":
    unittest.main()
