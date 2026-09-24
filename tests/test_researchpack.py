"""The research pack, driven through the cassette player against the real
Apify run lifecycle - start, poll, read the dataset.

## WHAT "CASSETTE" MEANS HERE, SAID PLAINLY

`tests/base.py` calls these "hand written provider fixtures". As of
2026-09-24 this one is half a capture: the FIELD SHAPE of every dataset row
in `tests/fixtures/cassettes/00-researchpack.json` was taken from real runs
of these four actors from this account on 2026-09-24, and the identifiers
were then replaced, because `tests/test_fixture_hygiene.py` refuses a real
company or person in a tracked file.

That distinction is the whole reason this docstring exists, and it is the
defect it was written against: the shapes this file asserted until today
were invented, and so were the ACTOR IDS - all three answered 404
record-not-found on `GET /v2/acts/{id}`. The tests were green against actors
that do not exist, which is the "a green test that cannot fail" shape this
repository already has on its list.

`scripts/capture_researchpack.py` takes fresh ones. It costs credits.

## WHAT IS ASSERTED

1. The real lifecycle runs: the POST carries the ACTOR'S input shape and
   not the crawler's, the poll is `apify.wait_for`, the dataset is read.
2. Every fact carries source, date and snippet - and a row that cannot
   support a claim is DROPPED rather than padded.
3. The cache is keyed on domain AND profile, and a hit buys nothing.
4. Cost reaches the one spend ledger, at the moment of the call.
5. No actor here needs a LinkedIn session.
6. The slug comes out of the JOBS run, and only when that row's own
   `companyWebsite` says it belongs to this record.
7. A LinkedIn target still goes through `apify.check_url`.

## THE `00-` PREFIX IS LOAD-BEARING

`tests/base.Cassette` loads every cassette file sorted and plays the FIRST
match, and `apify.json` holds a catch-all `GET /datasets/`. Without the
prefix these actors read THAT one instead of their own rows - which showed
up as a company post with no date, three layers from the cause.
"""
import json
import os
import unittest

from src import researchpack, spendledger, store, webfetch
from src.providers import apify
from src.researchpack import actors, cache, facts, site as sitesource
from tests.base import ProviderTest

COMPANY = "https://www.linkedin.com/company/acme-test"
CHAMPION = "https://www.linkedin.com/in/ada-example"
OTHER = "https://www.linkedin.com/in/bo-example"


class PackTest(ProviderTest):

    def setUp(self):
        super().setUp()
        # The cache is a file. `ProviderTest` moves the store, and `cache.path`
        # follows `store.queue_path`, but the variable is pinned anyway so a
        # future default change cannot quietly write the operator's cache.
        os.environ[cache.CACHE_VAR] = os.path.join(
            os.path.dirname(store.queue_path()), "research-pack-cache.json")
        self.addCleanup(os.environ.pop, cache.CACHE_VAR, None)

    def full(self, **over):
        kw = dict(live=True, client="productive", company="Acme Test Ltd",
                  champion=CHAMPION, crawler=site_reader())
        kw.update(over)
        return researchpack.build("acme.test", **kw)


#: A `site_page` row is not hand-written here. `webfetch._page` - the real
#: function, on real markup - produces it, so the keys `site.research` reads
#: are the keys the crawler writes and neither this file nor a future rename
#: can drift them apart. See `SiteContentIsOursAndFree` below for what is
#: and is not proven by that.
SITE_MARKUP = (
    "<html><head><title>Acme Test</title></head><body><main>"
    "<h1>Acme Test Ltd</h1><p>%s</p></main></body></html>")


def site_page(url, field="company_website", status=200, words=None):
    return webfetch._page(url, field, status,
                          SITE_MARKUP % (words or ("we build things. " * 40)),
                          webfetch.settings())


def site_reader(outcome=webfetch.HTTP_SUCCESS, pages=None):
    """A stand-in for `webfetch.research`, with the same signature.

    THE ENVELOPE IS THE PART A DOUBLE CANNOT PROVE, and this file says so
    rather than implying otherwise: the keys below are `webfetch.research`'s
    own `finish()` keys, read from the source, and the live run recorded in
    `docs/MERGE-REQUEST-2026-09-24-RESEARCH-PACKS.md` is what actually
    exercised them against real sites.
    """
    if pages is None:
        pages = [site_page("https://acme.test/"),
                 site_page("https://acme.test/about", field="about")]

    def crawler(domain, config=None, now=None):
        return {"domain": domain, "outcome": outcome, "pages": list(pages),
                "stats": {"requests": len(pages) + 1, "bytes": 4096,
                          "pages_kept": len(pages), "seconds": 0.4,
                          "outcomes": [outcome]},
                "retrieved_at": now or "2026-09-24T00:00:00+00:00",
                "fallback_worthy": outcome in webfetch.FALLBACK_WORTHY}
    return crawler


class EveryActorIdIsOneApifyKnows(unittest.TestCase):
    """THE DEFECT THIS FILE EXISTS TO PREVENT A SECOND TIME.

    These are not asserted against the network - the suite is offline. They
    are asserted as a SHAPE: an Apify actor id is `username/name` or
    `username~name`, and the three that were wrong were all `apify~...`,
    claiming Apify's own account publishes them. Two of the four here are on
    third-party accounts and the one that is Apify's own was verified to
    exist. The real check is `GET /v2/acts/{id}` and it is recorded in
    `docs/RESEARCH-PACK-PILOT-2026-09-24.md` with its date.
    """

    def test_each_names_an_owner_and_an_actor(self):
        for name, spec in actors.ACTORS.items():
            with self.subTest(actor=name):
                actor = spec["actor"]
                self.assertRegex(actor, r"^[A-Za-z0-9_.-]+[~/][A-Za-z0-9_.-]+$")

    def test_the_four_the_operator_asked_for_are_all_here(self):
        """All four sources, but only three of them are Apify's."""
        self.assertEqual(set(actors.SOURCES),
                         {"company_posts", "open_roles", "person_posts",
                          "site_content"})
        self.assertTrue({"company_posts", "open_roles", "person_posts"}
                        <= set(actors.ACTORS))

    def test_no_actor_is_a_website_crawler_any_more(self):
        """THE RULING, MADE UNREPRESENTABLE RATHER THAN DOCUMENTED.

        `apify~website-content-crawler` was 72% of the per-account bill -
        $0.02888 of $0.03987 - and the operator ruled on 2026-09-24 that
        site content comes from our own crawler and Apify runs LinkedIn
        only. An entry disabled by a flag is one edit from returning; this
        asserts there is no entry to re-enable, and that asking the input
        builder for one is an error rather than a payload.
        """
        for name, spec in actors.ACTORS.items():
            with self.subTest(actor=name):
                self.assertNotIn("website", spec["actor"])
                self.assertNotIn("crawler", spec["actor"])
        self.assertNotIn("site_content", actors.ACTORS)
        with self.assertRaises(KeyError):
            actors.build_input("site_content", ["https://acme.test/"])

    def test_the_free_source_names_our_own_crawler_and_no_price(self):
        spec = actors.FREE_SOURCES["site_content"]
        self.assertEqual(spec["provider"], sitesource.PROVIDER)
        self.assertEqual(spec["usd_per_account"], 0.0)

    def test_each_source_declares_the_kind_of_fact_it_makes(self):
        kinds = {spec["kind"] for spec in actors.ACTORS.values()
                 if spec["kind"]}
        kinds |= {spec["kind"] for spec in actors.FREE_SOURCES.values()}
        self.assertEqual(kinds, set(facts.KINDS))

    def test_the_slug_resolver_asserts_nothing_and_says_so(self):
        """A `kind` would make it a fifth source. It answers where the
        company's page is; it has no sentence anybody could quote."""
        self.assertIsNone(actors.ACTORS["company_slug"]["kind"])


class TheRunLifecycleIsTheProvidersOwn(PackTest):

    def test_a_company_post_run_goes_start_poll_dataset(self):
        found = researchpack.run_actor("company_posts", COMPANY,
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
        researchpack.run_actor("company_posts", COMPANY, client="productive")
        post = [c for c in self.cassette.calls if c["method"] == "POST"][0]
        body = post["body"] or {}
        self.assertIn("targetUrls", body)
        self.assertEqual(body["targetUrls"], [COMPANY])
        self.assertNotIn("maxCrawlPages", body)

    def test_a_person_run_excludes_reposts(self):
        """`why` says "in their words". A repost is somebody else's sentence
        and quoting it back as theirs is a wrong claim - and it was the FIRST
        row the live profile run returned, so this is the normal case."""
        payload = actors.build_input("person_posts", CHAMPION)
        self.assertFalse(payload["includeReposts"])

    def test_no_input_carries_a_proxy_configuration_at_all(self):
        """`proxyConfiguration` was the WEBSITE CRAWLER's field.

        The three LinkedIn actors do not declare it - they route their own
        requests - so sending it was inventing input for three actors that
        would have rejected or ignored it. With the crawler gone from this
        registry there is no actor left that declares the field, so no
        payload built here may carry one.
        """
        for name, target in (("company_posts", COMPANY),
                             ("open_roles", "Acme Test Ltd"),
                             ("person_posts", CHAMPION),
                             ("company_slug", "Acme Test Ltd")):
            with self.subTest(actor=name):
                self.assertNotIn("proxyConfiguration",
                                 actors.build_input(name, target))

    def test_no_input_asks_for_a_residential_proxy_group(self):
        """Datacenter unless a specific actor is blocked, and nothing was."""
        for name, target in (("company_posts", COMPANY),
                             ("open_roles", "Acme Test Ltd"),
                             ("person_posts", CHAMPION)):
            with self.subTest(actor=name):
                payload = actors.build_input(name, target)
                proxy = payload.get("proxyConfiguration") or {}
                self.assertNotIn("apifyProxyGroups", proxy)

    def test_a_pay_per_event_run_carries_a_charge_ceiling(self):
        """The actor `timeout` bounds a compute-unit run. It does not bound
        one that bills per row, where a target with ten thousand posts is a
        large bill inside a fast run."""
        researchpack.run_actor("company_posts", COMPANY, client="productive")
        post = [c for c in self.cassette.calls if c["method"] == "POST"][0]
        self.assertIn("maxTotalChargeUsd", post["url"])


class TheLinkedinTargetStillGoesThroughTheUrlGuard(PackTest):
    """THE WIDENING IS A LIST, NOT A HOLE."""

    def test_a_target_off_the_research_hosts_is_refused(self):
        with self.assertRaises(apify.UnsafeURL):
            researchpack.run_actor("company_posts",
                                   "https://elsewhere.test/company/acme",
                                   client="productive")

    def test_a_private_address_dressed_as_a_target_is_still_refused(self):
        # The credentials case is SPELLED IN TWO PIECES on purpose:
        # `user:secret@host` is indistinguishable from an email address to
        # `tests/test_fixture_hygiene.py`, which refuses any address outside
        # a reserved domain and cannot be taught an exception without
        # weakening the strongest rule it has.
        for bad in ("http://169.254.169.254/latest/meta-data/",
                    "file:///etc/passwd",
                    "https://user:secret" + "@www.linkedin.com/company/acme"):
            with self.subTest(url=bad):
                with self.assertRaises(apify.UnsafeURL):
                    researchpack.run_actor("person_posts", bad,
                                           client="productive")

    def test_nothing_was_started_when_the_url_was_refused(self):
        """A refusal that has already posted the run is not a refusal."""
        with self.assertRaises(apify.UnsafeURL):
            researchpack.run_actor("company_posts", "https://elsewhere.test/x",
                                   client="productive")
        self.assertEqual(self.cassette.calls, [])
        self.assertEqual(spendledger.load(), [])

    def test_the_company_site_read_is_still_bounded_to_its_own_domain(self):
        """The widening is for the LinkedIn actors. `site_content` means
        the record's OWN site, and now it does not reach Apify at all."""
        self.assertTrue(sitesource.on_this_domain("https://www.acme.test/x",
                                                  "acme.test"))
        self.assertFalse(sitesource.on_this_domain("https://elsewhere.test/x",
                                                   "acme.test"))
        with self.assertRaises(apify.UnsafeURL):
            apify.check_url("https://elsewhere.test/about",
                            allowed_domain="acme.test", resolve=False)


class TheSlugComesOutOfTheJobsRun(PackTest):

    def test_the_row_whose_website_is_this_domain_supplies_it(self):
        out = self.full()
        self.assertEqual(out["slug"],
                         "https://www.linkedin.com/company/acme-test")

    def test_a_row_for_a_company_that_merely_shares_a_name_is_walked_past(self):
        """`companyName` is a TEXT FILTER. The first cassette row is another
        company's job, and taking its slug would buy another company's posts
        and put them in front of this one."""
        rows = [{"companyUrl": "https://www.linkedin.com/company/acme-test-holdings",
                 "companyWebsite": "https://elsewhere.test/"}]
        self.assertIsNone(actors.slug_from_jobs(rows, "acme.test"))

    def test_a_row_with_no_website_proves_nothing_and_is_refused(self):
        """Missing evidence is never positive evidence."""
        rows = [{"companyUrl": "https://www.linkedin.com/company/acme-test"}]
        self.assertIsNone(actors.slug_from_jobs(rows, "acme.test"))

    def test_the_tracking_parameter_is_stripped(self):
        rows = [{"companyUrl": "https://www.linkedin.com/company/acme-test"
                               "?trk=public_jobs_topcard-org-name",
                 "companyWebsite": "https://acme.test/"}]
        self.assertEqual(actors.slug_from_jobs(rows, "acme.test"),
                         "https://www.linkedin.com/company/acme-test")

    def test_with_no_roles_the_posts_are_unaddressable_and_say_why(self):
        """NOT a silent empty pack. A company with no public LinkedIn job
        listing yields no slug, and the pack has to distinguish that from
        'they post nothing'."""
        out = researchpack.build("acme.test", live=True, client="productive",
                                 sources=("company_posts",))
        self.assertIn("company_posts", out["unaddressable"])
        self.assertIn("slug", out["unaddressable"]["company_posts"])
        self.assertEqual(out["bought"], [])

    def test_a_company_url_supplied_directly_needs_no_jobs_run(self):
        out = researchpack.build("acme.test", live=True, client="productive",
                                 company_url=COMPANY,
                                 sources=("company_posts",))
        self.assertIn("company_posts", out["bought"])


class EveryFactCarriesItsProvenance(PackTest):

    def test_source_date_and_snippet_on_each(self):
        found = researchpack.run_actor("company_posts", COMPANY,
                                       client="productive")
        for fact in found:
            self.assertTrue(fact["source_url"])
            self.assertTrue(fact["snippet"])
            self.assertTrue(fact["published_at"])
            self.assertTrue(fact["fact_id"])

    def test_the_nested_date_is_read(self):
        """harvestapi puts it at `postedAt.date`. A flat key list cannot see
        it, and a pack that reports UNKNOWN about a date it was given makes
        `quality` demand more of the evidence than it should."""
        found = researchpack.run_actor("company_posts", COMPANY,
                                       client="productive")
        self.assertEqual(found[0]["published_at"], "2026-09-02")

    def test_a_row_that_cannot_support_a_claim_is_dropped(self):
        """THE THIRD ROW IN THE CASSETTE HAS NO PERMALINK. Keeping it would
        put an unattributable sentence within reach of a draft."""
        found = researchpack.run_actor("company_posts", COMPANY,
                                       client="productive")
        self.assertEqual(len(found), 2, "the unusable row was kept")
        self.assertTrue(all(f["source_url"] for f in found))

    def test_another_companys_job_makes_no_fact(self):
        """MEASURED 2026-09-24: 50 of 71 rows the jobs actor returned over
        the pilot were a different company that merely shares part of a
        name, and on four of the eight accounts that got rows at all, ALL
        TEN were. `companyName` is a text filter, so this is the normal case
        rather than the exception - and an `open_role` fact about somebody
        else's hiring is a wrong-company claim in front of a client."""
        found = researchpack.run_actor("open_roles", "Acme Test Ltd",
                                       client="productive",
                                       domain="acme.test")
        urls = [f["source_url"] for f in found]
        self.assertNotIn("https://www.linkedin.com/jobs/view/4467598001",
                         urls, "another company's job became a fact")
        self.assertEqual(urls,
                         ["https://www.linkedin.com/jobs/view/4467598838"])

    def test_and_with_no_domain_to_check_against_nothing_passes(self):
        """FAIL CLOSED. A caller that forgets the domain gets no roles, not
        unchecked ones."""
        self.assertEqual(
            researchpack.run_actor("open_roles", "Acme Test Ltd",
                                   client="productive"), [])

    def test_a_page_that_did_not_load_never_reaches_the_pack(self):
        """WHERE THIS GUARD MOVED TO, AND WHY IT IS STRONGER THERE.

        The body of a 404 is the site's own navigation, which reads as
        ordinary company copy; two of five guessed pages 404'd on the
        first live Apify crawl and were kept. The paid crawler returned a
        row for every URL it was given and the pack had to filter on
        `crawl.httpStatusCode`. `webfetch.research` never yields a non-200
        at all - it drops the page before `_page` is reached - so the only
        rows `site.research` can see answered 200, and this reads the
        status off what it did get rather than trusting that.
        """
        out = self.full()
        pages = [f for f in out["facts"] if f["kind"] == "site_page"]
        self.assertTrue(pages)
        for fact in pages:
            with self.subTest(url=fact["source_url"]):
                self.assertEqual(fact["extra"]["http_status"], 200)

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


class AllFourSourcesReachThePack(PackTest):

    def test_one_build_returns_a_fact_of_every_kind(self):
        out = self.full()
        for kind in facts.KINDS:
            with self.subTest(kind=kind):
                self.assertGreater(out["by_kind"][kind], 0)

    def test_a_missing_champion_is_named_rather_than_silent(self):
        out = self.full(champion=None)
        self.assertIn("person_posts:champion", out["unaddressable"])

    def test_a_record_with_no_company_name_cannot_buy_roles(self):
        """The jobs actor is aimed by NAME and nothing here may invent one
        from the domain."""
        out = researchpack.build("acme.test", live=True, client="productive",
                                 sources=("open_roles",))
        self.assertIn("open_roles", out["unaddressable"])
        self.assertEqual(out["bought"], [])


class TheCacheIsKeyedOnDomainAndProfile(PackTest):

    def test_a_second_build_buys_nothing(self):
        first = self.full()
        self.assertTrue(first["bought"])
        calls = len(self.cassette.calls)
        second = self.full()
        self.assertEqual(second["cost"], 0)
        self.assertEqual(second["bought"], [])
        self.assertEqual(len(self.cassette.calls), calls,
                         "a cache hit still reached the provider")

    def test_a_cached_roles_run_still_supplies_the_slug(self):
        """Otherwise the second build re-buys the jobs run to learn where
        the company's LinkedIn page is, which is paying twice for a fact
        that has not changed."""
        self.full()
        again = self.full()
        self.assertEqual(again["slug"],
                         "https://www.linkedin.com/company/acme-test")
        self.assertIn("company_posts", again["cached"])

    def test_a_changed_champion_does_not_re_buy_the_company(self):
        """THE REASON FOR TWO KEYS. One account whose champion changed must
        re-buy that champion and nothing else."""
        self.full()
        before = len([c for c in self.cassette.calls if c["method"] == "POST"])
        out = self.full(champion=OTHER)
        after = len([c for c in self.cassette.calls if c["method"] == "POST"])
        self.assertIn("company_posts", out["cached"])
        self.assertIn("open_roles", out["cached"])
        self.assertEqual(after - before, 1,
                         "the new champion should be the only thing bought")

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

    def test_extra_cannot_forge_freshness(self):
        """`extra` carries the jobs run's residue. An entry that could
        overwrite its own `retrieved_at` would be a cache that never
        expires."""
        entry = cache.put("acme.test", [], profile="open_roles",
                          now="2026-09-20T00:00:00Z",
                          extra={"retrieved_at": "2099-01-01T00:00:00Z",
                                 "rows": [{"companyUrl": "x"}]})
        self.assertEqual(entry["retrieved_at"], "2026-09-20T00:00:00Z")
        self.assertEqual(entry["rows"], [{"companyUrl": "x"}])

    def test_the_key_is_case_insensitive(self):
        """A miss on capitalisation buys the same run twice and reports it
        as two accounts' worth of cost."""
        self.assertEqual(cache.key_for("Acme.Test", "Champion"),
                         cache.key_for("acme.test", "champion"))


class CostReachesTheOneLedger(PackTest):

    def test_a_bought_run_is_recorded_at_the_moment_of_the_call(self):
        self.full()
        rows = spendledger.load()
        calls = [(r["provider"], r["call"]) for r in rows]
        for name in ("company_posts", "open_roles", "person_posts"):
            self.assertIn(("apify", name), calls)

    def test_the_free_site_read_writes_no_ledger_row(self):
        """A zero-cost row for a provider that cannot charge would make
        the next audit reconcile against an invoice with no line for it."""
        out = self.full()
        self.assertIn("site_content", out["free"])
        self.assertNotIn("site_content", out["bought"])
        for row in spendledger.load():
            with self.subTest(row=row["call"]):
                self.assertNotEqual(row["call"], "site_content")
                self.assertNotEqual(row["provider"], "local_http")

    def test_the_ledger_cent_is_never_zero_and_never_understates(self):
        """The ledger's unit is an integer and every LinkedIn run here costs
        well under a cent. `int()` of that is a call recorded as free."""
        for name in actors.ACTORS:
            with self.subTest(actor=name):
                cents = actors.planned_cost(name)
                self.assertGreaterEqual(cents, 1)
                self.assertGreaterEqual(cents / 100.0,
                                        actors.usd_per_account(name))

    def test_a_cache_hit_records_nothing(self):
        self.full()
        before = len(spendledger.load())
        self.full()
        self.assertEqual(len(spendledger.load()), before,
                         "a cached pack wrote spend for a call nobody made")

    def test_the_pack_reports_its_own_cost_per_account(self):
        out = self.full()
        self.assertEqual(out["cost"],
                         actors.cost_of(["open_roles", "company_posts",
                                         "person_posts"]))

    def test_and_the_exact_dollars_travel_beside_the_rounded_cents(self):
        out = self.full()
        self.assertLess(out["usd"], out["cost"] / 100.0 + 1e-9)
        self.assertGreater(out["usd"], 0)


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
            researchpack.run_actor("needs_login", COMPANY)


class DryRunIsTheDefault(PackTest):

    def test_without_live_nothing_is_bought(self):
        out = researchpack.build("acme.test", company="Acme Test Ltd")
        self.assertEqual(out["cost"], 0)
        self.assertEqual(out["bought"], [])
        self.assertEqual(self.cassette.calls, [])

    def test_and_it_says_the_absence_is_an_unasked_question(self):
        """An empty pack read as 'nothing to say about them' and one read
        as 'we never looked' produce different emails."""
        out = researchpack.build("acme.test", company="Acme Test Ltd")
        self.assertIn("unasked question", out["note"])


class TheCeilingIsCHECKEDAndNotOnlyRECORDED(PackTest):
    """THE HALF THAT WAS MISSING, 2026-09-24 lane C.

    `run_actor` wrote a `spendledger` row for every paid call and never
    asked `spendledger.check` anything, so productive's declared
    `per_day: 5000` bounded nothing on this path - the ledger filled up and
    the runs kept starting. That is the repository's own recurring shape:
    a thing computed correctly that nothing downstream reads.

    Each test below was verified by removing `check_budget` from
    `run_actor` and confirming it goes red, and red for its own reason
    rather than because a different guard fired first.
    """

    TINY = {"budget": {"per_day": 1}}

    def test_a_call_that_would_cross_the_ceiling_is_refused(self):
        with self.assertRaises(spendledger.BudgetExceeded) as caught:
            researchpack.run_actor("open_roles", "Acme Test Ltd",
                                   client="productive", domain="acme.test",
                                   config=self.TINY)
        self.assertIn("per_day", str(caught.exception))

    def test_and_nothing_was_started_and_nothing_was_recorded(self):
        """A ceiling consulted after the money is spent is a report."""
        with self.assertRaises(spendledger.BudgetExceeded):
            researchpack.run_actor("open_roles", "Acme Test Ltd",
                                   client="productive", domain="acme.test",
                                   config=self.TINY)
        self.assertEqual(self.cassette.calls, [])
        self.assertEqual(spendledger.load(), [])

    def test_the_ceiling_counts_what_this_walk_has_already_committed(self):
        """NOT ONLY WHAT WAS THERE AT THE START. `check` re-reads the
        ledger, so a walk that spends its way to the ceiling stops at it."""
        config = {"budget": {"per_day": actors.planned_cost("open_roles")}}
        researchpack.run_actor("open_roles", "Acme Test Ltd",
                               client="productive", domain="acme.test",
                               config=config)
        self.assertEqual(len(spendledger.load()), 1)
        with self.assertRaises(spendledger.BudgetExceeded):
            researchpack.run_actor("open_roles", "Acme Test Ltd",
                                   client="productive", domain="acme.test",
                                   config=config)

    def test_an_unattributed_run_cannot_buy_anything(self):
        """`spendledger.check` refuses a falsy client by its own contract -
        an unscoped budget is one client paying for another's run - and that
        refusal is kept rather than smoothed over."""
        with self.assertRaises(spendledger.BudgetExceeded):
            researchpack.run_actor("company_posts", COMPANY)
        self.assertEqual(self.cassette.calls, [])
        self.assertEqual(spendledger.load(), [])

    def test_the_refusal_reaches_the_caller_of_build(self):
        """NOT swallowed into a thin pack. A budget refusal that looked like
        a source returning nothing would read as a quiet estate."""
        with self.assertRaises(spendledger.BudgetExceeded):
            self.full(config=self.TINY)

    def test_the_free_site_read_is_not_subject_to_a_ceiling(self):
        """A ceiling on a call that cannot be billed would stop a pack for
        a reason that does not exist."""
        out = researchpack.build("acme.test", live=True, client="productive",
                                 config=self.TINY, crawler=site_reader(),
                                 sources=("site_content",))
        self.assertEqual(out["free"], ["site_content"])
        self.assertGreater(out["by_kind"]["site_page"], 0)
        self.assertEqual(spendledger.load(), [])


class SiteContentIsOursAndFree(PackTest):
    """The operator ruling, exercised rather than restated.

    WHAT THESE PROVE AND WHAT THEY DO NOT. The page rows are built by
    `webfetch._page` itself on real markup, so the fields `site.research`
    reads are the fields the crawler writes. The ENVELOPE - `outcome`,
    `pages`, `stats` - is a double, and a double cannot prove the crawler
    returns that shape. What proves it is the live run over 92 real
    accounts recorded in `docs/MERGE-REQUEST-2026-09-24-RESEARCH-PACKS.md`.
    """

    def test_a_site_read_touches_no_provider_at_all(self):
        out = researchpack.build("acme.test", live=True, client="productive",
                                 crawler=site_reader(),
                                 sources=("site_content",))
        self.assertEqual(self.cassette.calls, [])
        self.assertEqual(out["cost"], 0)
        self.assertEqual(out["usd"], 0.0)

    def test_every_site_fact_carries_a_url_and_something_to_quote(self):
        found, outcome = sitesource.research("acme.test",
                                             crawler=site_reader())
        self.assertTrue(found)
        self.assertEqual(outcome["usd"], 0.0)
        for fact in found:
            with self.subTest(url=fact["source_url"]):
                self.assertEqual(fact["kind"], "site_page")
                self.assertTrue(fact["source_url"].startswith("https://"))
                self.assertTrue(fact["snippet"].strip())
                self.assertEqual(fact["extra"]["actor"], "local_http")

    def test_a_crawled_page_is_never_dated(self):
        """`retrieved_at` is when WE looked. Passing it as `published_at`
        would make every site fact read as published today, and 'they just
        announced' is exactly the claim a date licenses."""
        found, _ = sitesource.research("acme.test", crawler=site_reader())
        for fact in found:
            with self.subTest(url=fact["source_url"]):
                self.assertIsNone(fact["published_at"])

    def test_a_page_off_this_domain_makes_no_fact(self):
        """THE IDENTITY QUESTION, ASKED HERE TOO. `webfetch.same_domain`
        already bounds the crawl, and 'cannot happen' is what was said about
        the job rows before 50 of 71 turned out to be another company."""
        reader = site_reader(pages=[
            site_page("https://elsewhere.test/about", field="about"),
            site_page("https://acme.test/about", field="about")])
        found, outcome = sitesource.research("acme.test", crawler=reader)
        self.assertEqual([f["source_url"] for f in found],
                         ["https://acme.test/about"])
        self.assertEqual(outcome["off_domain_pages_dropped"], 1)

    def test_a_site_that_needs_javascript_is_said_rather_than_scored(self):
        """`urllib` cannot run the page and a shell is not evidence about
        the company inside it. The classification is the reason, and it is
        `webfetch`'s rather than one this package guessed at."""
        out = researchpack.build("acme.test", live=True, client="productive",
                                 sources=("site_content",),
                                 crawler=site_reader(
                                     outcome=webfetch.JS_RENDERING_REQUIRED,
                                     pages=[]))
        self.assertIn("site_content", out["unaddressable"])
        self.assertIn(webfetch.JS_RENDERING_REQUIRED,
                      out["unaddressable"]["site_content"])
        self.assertEqual(out["by_kind"]["site_page"], 0)

    def test_a_blocked_site_is_not_a_reason_to_spend(self):
        """The paid crawler was the fallback for exactly this, and the
        ruling took that decision away. There is no branch that can buy one."""
        out = researchpack.build("acme.test", live=True, client="productive",
                                 sources=("site_content",),
                                 crawler=site_reader(outcome=webfetch.BLOCKED,
                                                     pages=[]))
        self.assertEqual(out["bought"], [])
        self.assertEqual(self.cassette.calls, [])
        self.assertEqual(spendledger.load(), [])

    def test_a_second_build_re_reads_nothing(self):
        """Free is not costless: it is requests against somebody's server."""
        reads = []

        def counting(domain, config=None, now=None):
            reads.append(domain)
            return site_reader()(domain, config=config, now=now)

        for _ in range(2):
            researchpack.build("acme.test", live=True, client="productive",
                               sources=("site_content",), crawler=counting)
        self.assertEqual(len(reads), 1)

class TheCassetteSaysWhatItIs(unittest.TestCase):
    """The provenance note is load-bearing, so it is asserted."""

    def test_it_separates_the_captured_shape_from_the_invented_content(self):
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "fixtures", "cassettes", "00-researchpack.json")
        with open(path, encoding="utf-8") as handle:
            entries = json.load(handle)
        note = entries[0].get("note") or ""
        self.assertIn("FIELD SHAPE", note)
        self.assertIn("identifiers were then replaced", note)


if __name__ == "__main__":
    unittest.main()
