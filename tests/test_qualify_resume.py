"""An interrupted 5,000-company batch, and what must survive the interruption.

The failure this file exists to catch is the expensive one: a batch that stops
at company 2,731 and, on restart, either re-derives everything (slow, and it
invalidates an approval that was fine) or loses the companies it had already
judged. Both look like success from the outside.

Everything here is offline. Qualification spends nothing, which is the whole
reason it is safe to re-run at all.
"""
import contextlib
import io
import unittest

from src import companies, dmplan, icp, qualify, routing, store
from tests.campaignbase import CampaignTest


class ResumeTest(CampaignTest):
    SIZE = 120

    def batch(self, size=None):
        recs = companies.dataset(size or self.SIZE, client="productive")
        store.save(recs)
        return store.load()

    def qualify(self, recs=None, **kw):
        """Qualify and persist, the way the CLI does.

        Saving `recs` rather than the returned companies matters: with a
        `limit`, the result carries only the companies it reached, and writing
        that list back would delete every company the run had not got to yet.
        `run` mutates the records in place, so the full list is already
        up to date.
        """
        with store.transaction() as recs_:
            target = recs if recs is not None else recs_
            result = qualify.run(target, client="productive",
                                 config=self.config, **kw)
            if recs is not None:
                recs_[:] = recs
        return result


class TestStoppingEarly(ResumeTest):
    def test_a_limit_stops_where_it_was_told_to(self):
        self.batch()
        result = self.qualify(limit=40)
        self.assertEqual(result["processed"], 40)

    def test_the_companies_it_did_not_reach_are_untouched(self):
        self.batch()
        self.qualify(limit=40)
        unprocessed = [r for r in store.load() if not r.get("qualification")]
        self.assertEqual(len(unprocessed), self.SIZE - 40)

    def test_an_unreached_company_reports_not_processed(self):
        self.batch()
        self.qualify(limit=40)
        unreached = [r for r in store.load() if not r.get("qualification")]
        self.assertEqual(qualify.state_of(unreached[0]), dmplan.NOT_PROCESSED)

    def test_nothing_is_lost_by_stopping(self):
        self.batch()
        self.qualify(limit=40)
        self.assertEqual(len(store.load()), self.SIZE)


class TestResuming(ResumeTest):
    def test_the_second_run_finishes_what_the_first_started(self):
        self.batch()
        self.qualify(limit=40)
        second = self.qualify()
        self.assertEqual(second["processed"], self.SIZE - 40)
        self.assertEqual(second["reused"], 40)

    def test_every_company_is_classified_after_resuming(self):
        self.batch()
        self.qualify(limit=40)
        self.qualify()
        self.assertTrue(all(r.get("qualification") for r in store.load()))

    def test_resuming_does_not_re_derive_settled_companies(self):
        """The saving that makes a 5,000-company restart cheap."""
        self.batch()
        self.qualify(limit=40)
        second = self.qualify()
        self.assertEqual(second["reused"], 40)

    def test_a_completed_batch_re_run_does_no_work_at_all(self):
        self.batch()
        self.qualify()
        again = self.qualify()
        self.assertEqual(again["processed"], 0)
        self.assertEqual(again["reused"], self.SIZE)

    def test_no_record_is_lost_across_an_interrupted_run(self):
        before = {r["id"] for r in self.batch()}
        self.qualify(limit=40)
        self.qualify(limit=40)
        self.qualify()
        self.assertEqual({r["id"] for r in store.load()}, before)


class TestDeterminism(ResumeTest):
    """A resumed batch must reach the verdicts an uninterrupted one would."""

    def verdicts(self):
        return {r["id"]: (r["qualification"]["verdict"]["icp_status"],
                          r["qualification"]["verdict"]["icp_tier"],
                          r["qualification"]["verdict"]["icp_score"])
                for r in store.load() if r.get("qualification")}

    def test_an_interrupted_batch_reaches_the_same_verdicts(self):
        self.batch()
        self.qualify()
        whole = self.verdicts()

        store.save(companies.dataset(self.SIZE, client="productive"))
        self.qualify(limit=40)
        self.qualify(limit=40)
        self.qualify()
        self.assertEqual(self.verdicts(), whole)

    def test_an_interrupted_batch_reaches_the_same_segments(self):
        self.batch()
        self.qualify()
        whole = {r["id"]: r["qualification"].get("segment_key")
                 for r in store.load()}

        store.save(companies.dataset(self.SIZE, client="productive"))
        self.qualify(limit=40)
        self.qualify()
        resumed = {r["id"]: r["qualification"].get("segment_key")
                   for r in store.load()}
        self.assertEqual(resumed, whole)

    def test_scoring_the_same_company_twice_gives_the_same_answer(self):
        rec = self.batch(20)[0]
        self.assertEqual(icp.score(rec, self.config)["icp_score"],
                         icp.score(rec, self.config)["icp_score"])


class TestRequalification(ResumeTest):
    def test_a_company_whose_facts_changed_is_re_derived(self):
        self.batch()
        self.qualify()
        with store.transaction() as recs:
            rec = store.get(recs[0]["id"], recs)
            rec["company_facts"]["employees"] = 999
        again = self.qualify()
        self.assertEqual(again["processed"], 1)
        self.assertEqual(again["reused"], self.SIZE - 1)

    def test_force_re_derives_everything(self):
        self.batch()
        self.qualify()
        again = self.qualify(force=True)
        self.assertEqual(again["processed"], self.SIZE)
        self.assertEqual(again["reused"], 0)


class TestApprovalSurvivesAResume(ResumeTest):
    """Section 18: the approval must mean "this plan", across a restart."""

    def entries(self):
        result = self.qualify()
        return result["companies"]

    def test_an_approval_stays_current_when_nothing_changed(self):
        self.batch()
        batch = {}
        entries = self.entries()
        dmplan.approve(batch, entries, by="operator", config=self.config)
        current, why = dmplan.is_current(batch, self.entries())
        self.assertTrue(current, why)

    def test_the_fingerprint_survives_a_reload_from_disk(self):
        """It must be computed from stored state, not from run state."""
        self.batch()
        first = dmplan.fingerprint(self.entries())
        store.save(store.load())
        self.assertEqual(dmplan.fingerprint(self.entries()), first)

    def test_requalifying_with_changed_facts_makes_the_approval_stale(self):
        self.batch()
        batch = {}
        dmplan.approve(batch, self.entries(), by="operator", config=self.config)
        with store.transaction() as recs:
            for rec in recs[:20]:
                rec["company_facts"]["employees"] = 4
                rec["company_facts"]["description"] = "We sell a SaaS platform."
        current, why = dmplan.is_current(batch, self.entries())
        self.assertFalse(current)
        self.assertIn("changed after approval", why)

    def test_a_changed_segment_assignment_makes_the_approval_stale(self):
        """The one material field that is not derivable from one company."""
        entries = [
            {"record": {"id": "a", "domain": "a.test"},
             "verdict": {"icp_status": icp.QUALIFIED, "icp_tier": icp.TIER_A},
             "persona_plan": {"max_contacts_to_enrich": 3,
                              "target_titles": ["CEO"], "cap_reason": "tier A"},
             "segment_key": "PRODUCTIVE-UK-DIGITAL-50_99-OPERATIONS"},
        ]
        batch = {}
        dmplan.approve(batch, entries, by="operator")
        self.assertTrue(dmplan.is_current(batch, entries)[0])
        entries[0]["segment_key"] = "PRODUCTIVE-UK-DIGITAL-100_199-OPERATIONS"
        self.assertFalse(dmplan.is_current(batch, entries)[0])

    def test_nothing_may_be_enriched_after_the_plan_goes_stale(self):
        self.batch()
        batch = {}
        entries = self.entries()
        dmplan.approve(batch, entries, by="operator", config=self.config)
        with store.transaction() as recs:
            for rec in recs[:20]:
                rec["company_facts"]["employees"] = 4
        fresh = self.entries()
        qualified = next(e for e in fresh
                         if e["verdict"]["icp_status"] == icp.QUALIFIED)
        allowed, why = dmplan.may_enrich(batch, fresh, qualified["record"],
                                         qualified["verdict"], self.config)
        self.assertFalse(allowed, why)


class TestTheCliPersists(ResumeTest):
    """Without the write, the whole resume path above is unreachable.

    `qualify.main` ran with `store_result=False` and never saved, so every
    verdict it computed was discarded: `--limit` could not be continued and
    `needs_work` had no stored fingerprint to compare against, which meant a
    5,000-company batch re-derived all 5,000 on every invocation.
    """

    def cli(self, *args):
        """Run the CLI without its output landing in the test log."""
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            return qualify.main(list(args))

    def test_the_cli_writes_its_verdicts_back(self):
        self.batch()
        self.cli("--client", "productive", "--json")
        self.assertTrue(all(r.get("qualification") for r in store.load()))

    def test_a_limited_run_keeps_the_companies_it_did_not_reach(self):
        self.batch()
        self.cli("--client", "productive", "--limit", "30", "--json")
        recs = store.load()
        self.assertEqual(len(recs), self.SIZE)
        self.assertEqual(sum(1 for r in recs if r.get("qualification")), 30)

    def test_a_second_cli_run_continues_rather_than_restarting(self):
        self.batch()
        self.cli("--client", "productive", "--limit", "30", "--json")
        self.cli("--client", "productive", "--json")
        self.assertTrue(all(r.get("qualification") for r in store.load()))

    def test_dry_run_writes_nothing(self):
        self.batch()
        self.cli("--client", "productive", "--dry-run", "--json")
        self.assertFalse(any(r.get("qualification") for r in store.load()))


class TestNothingSpends(ResumeTest):
    def test_qualification_plans_spend_without_incurring_it(self):
        self.batch()
        result = self.qualify()
        plan = dmplan.for_batch(result["companies"], self.config)
        self.assertGreater(plan["expected_credits"], 0)
        self.assertEqual(sum(len(r.get("contacts") or [])
                             for r in store.load()), 0)

    def test_no_rejected_or_review_company_is_planned_a_contact(self):
        self.batch()
        for entry in self.qualify()["companies"]:
            if entry["verdict"]["icp_status"] != icp.QUALIFIED:
                self.assertEqual(
                    entry["persona_plan"]["max_contacts_to_enrich"], 0,
                    entry["record"]["id"])

    def test_planned_contacts_never_exceed_the_tier_cap(self):
        self.batch()
        caps = routing.settings(self.config)["caps"]
        for entry in self.qualify()["companies"]:
            self.assertLessEqual(
                entry["persona_plan"]["max_contacts_to_enrich"],
                caps.get(entry["verdict"]["icp_tier"], 0),
                entry["record"]["id"])

    def test_the_module_never_writes_a_contact(self):
        import inspect
        source = inspect.getsource(qualify)
        for banned in ("contactout.", "aiark.", "apify.", "reoon.",
                       "requests.", "urlopen"):
            self.assertNotIn(banned, source, banned)


if __name__ == "__main__":
    unittest.main()
