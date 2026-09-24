"""The research pack, driven through the cassette player against the real
Apify run lifecycle - start, poll, read the dataset.

## WHAT "CASSETTE" MEANS HERE, SAID PLAINLY

`tests/base.py` calls these "hand written provider fixtures", and
`tests/fixtures/cassettes/00-researchpack.json` is hand written to Apify's
documented schema. **It is not captured from a live run.** There is nothing
to capture from: `providers/apify.start_run` records that every run this
repository ever started was rejected with 400 `invalid-input` for a missing
`proxyConfiguration`, so no Apify actor has ever returned evidence here.

`scripts/capture_researchpack.py` takes the real ones. It costs credits and
has not been run.

That distinction is the whole reason this docstring exists. A fixture
presented as a capture is the "fixtures are invented" failure this
repository already has on its list, and it is worse for a provider whose
output shape nobody in this codebase has ever actually seen.

## WHAT IS ASSERTED

1. The real lifecycle runs: the POST carries the ACTOR'S input shape and
   not the crawler's, the poll is `apify.wait_for`, the dataset is read.
2. Every fact carries source, date and snippet - and a row that cannot
   support a claim is DROPPED rather than padded.

3. The cache is keyed on domain AND profile, and a hit buys nothing.
4. Cost reaches the one spend ledger, at the moment of the call.
5. No actor here needs a LinkedIn session.

## THE `00-` PREFIX IS LOAD-BEARING

`tests/base.Cassette` loads every cassette file sorted and plays the FIRST
match, and `apify.json` holds a catch-all `GET /datasets/`. Without the
prefix these actors read THAT one instead of their own rows - which showed
up as a company post with no date, three layers from the cause.
"""
import json
import os
import unittest

from src import researchpack, spendledger, store
from src.researchpack import actors, cache, facts
from tests.base import ProviderTest


class PackTest(ProviderTest):

    def setUp(self):
        super().setUp()
        # The cache is a file. `ProviderTest` moves the store, and `cache.path`
        # follows `store.queue_path`, but the variable is pinned anyway so a
        # future default change cannot quietly write the operator's cache.
        os.environ[cache.CACHE_VAR] = os.path.join(
            os.path.dirname(store.queue_path()), "research-pack-cache.json")
        self.addCleanup(os.environ.pop, cache.CACHE_VAR, None)


class TheRunLifecycleIsTheProvidersOwn(PackTest):

    def test_a_company_post_run_goes_start_poll_dataset(self):
        found = researchpack.run_actor(
            "company_posts", "https://www.linkedin.test/company/acme",
            client="productive")
        methods = [(c["method"], c["url"]) for c in self.cassette.calls]
        self.assertTrue(any(m == "POST" and "/runs" in u
                            for m, u in methods), methods)
        self.assertTrue(any(m == "GET" and "/actor-runs/" in u
                            for m, u in methods), methods)
        self.assertTrue(any(m == "GET" and "/datasets/" in u
                            for m, u in methods), methods)
        self.assertEqual(len(found), 2)

    def test_the_post_carries_the_actors_input_not_the_crawlers(self):
        """`apify.start_run` builds `startUrls`/`maxCrawlPages`. Sending
        that to a posts actor is a 400, and the reason this package builds
        its own input rather than reusing that function."""
        researchpack.run_actor(
            "company_posts", "https://www.linkedin.test/company/acme",
            client="productive")
        post = [c for c in self.cassette.calls if c["method"] == "POST"][0]
        body = post["body"] or {}
        self.assertIn("companyUrl", body)
        self.assertNotIn("startUrls", body)
        self.assertNotIn("maxCrawlPages", body)

    def test_every_run_carries_the_proxy_configuration(self):
        """WITHOUT IT THE RUN IS REJECTED BEFORE IT STARTS, which is how
        this provider appeared to work for months and returned nothing."""
        for name, target in (("company_posts", "https://li.test/company/a"),
                             ("open_roles", "acme.test"),
                             ("person_posts", "https://li.test/in/ada")):
            with self.subTest(actor=name):
                payload = actors.build_input(name, target)
                self.assertEqual(payload["proxyConfiguration"],
                                 {"useApifyProxy": True})


class EveryFactCarriesItsProvenance(PackTest):

    def test_source_date_and_snippet_on_each(self):
        found = researchpack.run_actor(
            "company_posts", "https://www.linkedin.test/company/acme",
            client="productive")
        for fact in found:
            self.assertTrue(fact["source_url"])
            self.assertTrue(fact["snippet"])
            self.assertTrue(fact["published_at"])
            self.assertTrue(fact["fact_id"])

    def test_a_row_that_cannot_support_a_claim_is_dropped(self):
        """THE THIRD ROW IN THE CASSETTE HAS NO URL. Keeping it would put
        an unattributable sentence within reach of a draft."""
        found = researchpack.run_actor(
            "company_posts", "https://www.linkedin.test/company/acme",
            client="productive")
        self.assertEqual(len(found), 2, "the unusable row was kept")
        self.assertTrue(all(f["source_url"] for f in found))

    def test_an_undated_post_is_none_rather_than_today(self):
        """Inventing a date makes 'they just announced' a lie the copy can
        lean on."""
        fact = facts.make("company_post", "https://x.test/1", None, "words")
        self.assertIsNone(fact["published_at"])

    def test_the_id_is_stable_across_runs(self):
        """A draft that cited a fact last week must still trace this week."""
        first = facts.make("company_post", "https://x.test/1", "2026-09-01",
                           "We opened a Berlin office.")
        again = facts.make("company_post", "https://x.test/1", "2026-09-02",
                           "  We opened   a Berlin office. ")
        self.assertEqual(first["fact_id"], again["fact_id"])


class TheCacheIsKeyedOnDomainAndProfile(PackTest):

    def test_a_second_build_buys_nothing(self):
        first = researchpack.build("acme.test", live=True, client="productive")
        self.assertTrue(first["bought"])
        calls = len(self.cassette.calls)
        second = researchpack.build("acme.test", live=True,
                                    client="productive")
        self.assertEqual(second["cost"], 0)
        self.assertEqual(second["bought"], [])
        self.assertEqual(len(self.cassette.calls), calls,
                         "a cache hit still reached the provider")

    def test_a_changed_champion_does_not_re_buy_the_company(self):
        """THE REASON FOR TWO KEYS. One account whose champion changed must
        re-buy that champion and nothing else."""
        researchpack.build("acme.test", live=True, client="productive",
                           champion="https://li.test/in/ada")
        before = len([c for c in self.cassette.calls
                      if c["method"] == "POST"])
        out = researchpack.build("acme.test", live=True, client="productive",
                                 champion="https://li.test/in/bo")
        after = len([c for c in self.cassette.calls if c["method"] == "POST"])
        self.assertIn("company_posts", out["cached"])
        self.assertIn("open_roles", out["cached"])
        self.assertEqual(after - before, 0,
                         "a new champion url re-bought the company actors "
                         "as well; the profile is part of the key so that "
                         "it cannot")

    def test_the_ttl_is_thirty_days(self):
        self.assertEqual(cache.TTL_DAYS, 30)

    def test_an_entry_past_the_ttl_is_not_served(self):
        cache.put("acme.test", [], profile="company_posts",
                  now="2026-08-01T00:00:00Z")
        self.assertIsNone(cache.get("acme.test", profile="company_posts",
                                    now="2026-09-24T00:00:00Z"))

    def test_an_entry_inside_the_ttl_is(self):
        """THE CONTROL: if nothing were ever served the test above passes
        and the cache is decoration."""
        cache.put("acme.test", [], profile="company_posts",
                  now="2026-09-20T00:00:00Z")
        self.assertIsNotNone(cache.get("acme.test", profile="company_posts",
                                       now="2026-09-24T00:00:00Z"))

    def test_the_key_is_case_insensitive(self):
        """A miss on capitalisation buys the same run twice and reports it
        as two accounts' worth of cost."""
        self.assertEqual(cache.key_for("Acme.Test", "Champion"),
                         cache.key_for("acme.test", "champion"))


class CostReachesTheOneLedger(PackTest):

    def test_a_bought_run_is_recorded_at_the_moment_of_the_call(self):
        researchpack.build("acme.test", live=True, client="productive")
        rows = spendledger.load()
        calls = [(r["provider"], r["call"], r["expected_cost"]) for r in rows]
        self.assertIn(("apify", "company_posts", 5), calls)
        self.assertIn(("apify", "open_roles", 4), calls)

    def test_a_cache_hit_records_nothing(self):
        researchpack.build("acme.test", live=True, client="productive")
        before = len(spendledger.load())
        researchpack.build("acme.test", live=True, client="productive")
        self.assertEqual(len(spendledger.load()), before,
                         "a cached pack wrote spend for a call nobody made")

    def test_the_pack_reports_its_own_cost_per_account(self):
        out = researchpack.build("acme.test", live=True, client="productive")
        self.assertEqual(out["cost"], actors.cost_of(["company_posts",
                                                      "open_roles"]))


class NothingHereNeedsALoggedInSession(PackTest):

    def test_no_actor_declares_one(self):
        for name, spec in actors.ACTORS.items():
            with self.subTest(actor=name):
                self.assertFalse(spec["needs_session"])

    def test_and_one_that_did_would_be_refused(self):
        """THE CONTROL. Without it this is a test that every dict has False
        in it, which stays green when the refusal is deleted."""
        actors.ACTORS["needs_login"] = dict(actors.ACTORS["company_posts"],
                                            needs_session=True)
        self.addCleanup(actors.ACTORS.pop, "needs_login", None)
        with self.assertRaises(researchpack.PackRefused):
            researchpack.run_actor("needs_login", "https://li.test/x")


class DryRunIsTheDefault(PackTest):

    def test_without_live_nothing_is_bought(self):
        out = researchpack.build("acme.test")
        self.assertEqual(out["cost"], 0)
        self.assertEqual(out["bought"], [])
        self.assertEqual(self.cassette.calls, [])

    def test_and_it_says_the_absence_is_an_unasked_question(self):
        """An empty pack read as 'nothing to say about them' and one read
        as 'we never looked' produce different emails."""
        out = researchpack.build("acme.test")
        self.assertIn("unasked question", out["note"])


class TheCassetteSaysWhatItIs(unittest.TestCase):
    """The provenance note is load-bearing, so it is asserted."""

    def test_it_does_not_claim_to_be_a_live_capture(self):
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "fixtures", "cassettes", "00-researchpack.json")
        with open(path, encoding="utf-8") as handle:
            entries = json.load(handle)
        note = entries[0].get("note") or ""
        self.assertIn("NOT captured from a live run", note)
        self.assertIn("capture_researchpack", note)


if __name__ == "__main__":
    unittest.main()
