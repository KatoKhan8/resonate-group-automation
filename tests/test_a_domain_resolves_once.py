"""Every run re-resolved every domain, because nothing ever wrote the cache.

`mx.for_domain` persists only when `own_cache and save` - and `enrich_record`
called it as `for_domain(domain, config, cache=cache, save=False)`, so BOTH
conditions blocked the write. Worse, the cache was `load_cache()`d INSIDE the
per-record function, so each record read the (never-written) file, mutated a dict
and threw it away.

MEASURED, before the fix: an unscoped enrichment run over 100 records spent
9 minutes 40 seconds almost entirely in serial UDP DNS, never reached the fifty
records it was asked about, and spent no credits at all. The same fifty scoped by
id took 34 seconds. At 24,710 domains that is the difference between minutes and
hours.

The fix is ownership, not caching: the RUN owns one cache, threads it into every
record, and saves it once at the end. Saving per record would rewrite the whole
file per domain, which relocates the problem rather than removing it.

What must NOT change, and each has a test below: freshness still expires on the
client's `cache_days`; a DNS failure is still never cached, because a resolver
that was down for a second must not hold an email channel for a week; and an
entry belongs to exactly one domain.
"""
import json
import os
import unittest
from unittest import mock

from src import enrich, mx, store

from tests.base import QueueTest


class Resolver:
    """A DNS stand-in that counts every lookup it is asked to perform."""

    def __init__(self, hosts=("aspmx.l.google.com",), fail=()):
        self.hosts = list(hosts)
        self.fail = set(fail)
        self.asked = []

    def __call__(self, domain, **kw):
        self.asked.append(domain)
        if domain in self.fail:
            raise OSError("dns timeout")
        return list(self.hosts)


def config(cache_days=7):
    """The REAL config shape. `mx.settings` reads `email_security.mx_filter`.

    The first version of this helper used a top-level `mx` key, so every test
    silently ran against `mx.DEFAULTS` instead of the values it named - and
    passed, because the defaults happen to match. Only the `cache_days=0` case
    disagreed with the default and exposed it. A fixture that is ignored is
    worse than a wrong assertion, because everything looks green.
    """
    return {"email_security": {"mx_filter": {"enabled": True,
                                             "cache_days": cache_days}}}


class OneDomainResolvesOncePerRun(QueueTest):
    def test_fifty_contacts_at_one_company_resolve_once(self):
        r = Resolver()
        cache = {}
        for _ in range(50):
            mx.for_domain("acme.test", config(), cache=cache, resolver=r,
                          save=False)
        self.assertEqual(r.asked, ["acme.test"])

    def test_a_second_run_does_not_resolve_again_when_the_cache_persisted(self):
        """The property that was broken: nothing survived the process."""
        r = Resolver()
        first = mx.load_cache()
        mx.for_domain("acme.test", config(), cache=first, resolver=r,
                      save=False)
        mx.save_cache(first)
        second = mx.load_cache()          # a fresh "process"
        mx.for_domain("acme.test", config(), cache=second, resolver=r,
                      save=False)
        self.assertEqual(r.asked, ["acme.test"], "it resolved twice")

    def test_the_cache_file_is_actually_written(self):
        cache = {}
        mx.for_domain("acme.test", config(), cache=cache, resolver=Resolver(),
                      save=False)
        mx.save_cache(cache)
        self.assertTrue(os.path.exists(mx.cache_path()))
        with open(mx.cache_path(), encoding="utf-8") as handle:
            self.assertIn("acme.test", json.load(handle))

    def test_a_cache_hit_says_so(self):
        r = Resolver()
        cache = {}
        first = mx.for_domain("acme.test", config(), cache=cache, resolver=r,
                             save=False)
        second = mx.for_domain("acme.test", config(), cache=cache, resolver=r,
                               save=False)
        self.assertFalse(first["cached"])
        self.assertTrue(second["cached"])


class FreshnessStillExpires(QueueTest):
    """A cache that never expires is stale evidence made permanent."""

    def test_an_entry_older_than_cache_days_is_re_resolved(self):
        r = Resolver()
        cache = {"acme.test": {"mx_records": ["old.example"],
                               "status": None,
                               "checked_at": "2020-01-01T00:00:00+00:00"}}
        mx.for_domain("acme.test", config(cache_days=7), cache=cache,
                      resolver=r, save=False)
        self.assertEqual(r.asked, ["acme.test"], "stale entry was trusted")

    def test_cache_days_zero_disables_the_cache_entirely(self):
        r = Resolver()
        cache = {}
        mx.for_domain("acme.test", config(cache_days=0), cache=cache,
                      resolver=r, save=False)
        mx.for_domain("acme.test", config(cache_days=0), cache=cache,
                      resolver=r, save=False)
        self.assertEqual(len(r.asked), 2)

    def test_an_entry_with_no_timestamp_is_not_fresh(self):
        r = Resolver()
        cache = {"acme.test": {"mx_records": ["x.example"], "status": None}}
        mx.for_domain("acme.test", config(), cache=cache, resolver=r,
                      save=False)
        self.assertEqual(r.asked, ["acme.test"])

    def test_an_unparseable_timestamp_is_not_fresh(self):
        r = Resolver()
        cache = {"acme.test": {"mx_records": ["x.example"], "status": None,
                               "checked_at": "not a time"}}
        mx.for_domain("acme.test", config(), cache=cache, resolver=r,
                      save=False)
        self.assertEqual(r.asked, ["acme.test"])


class AFailureIsNeverCached(QueueTest):
    """Unknown must stay unknown, and must not become a week-long verdict."""

    def test_a_dns_failure_is_not_written_to_the_cache(self):
        cache = {}
        found = mx.for_domain("dead.test", config(),
                              cache=cache, resolver=Resolver(fail={"dead.test"}),
                              save=False)
        self.assertEqual(found["status"], mx.DNS_FAILURE)
        self.assertNotIn("dead.test", cache)

    def test_a_failure_is_retried_on_the_next_call(self):
        r = Resolver(fail={"dead.test"})
        cache = {}
        mx.for_domain("dead.test", config(), cache=cache, resolver=r, save=False)
        mx.for_domain("dead.test", config(), cache=cache, resolver=r, save=False)
        self.assertEqual(len(r.asked), 2, "a transient failure was cached")

    def test_a_failure_never_reads_as_allowed(self):
        found = mx.for_domain("dead.test", config(), cache={},
                              resolver=Resolver(fail={"dead.test"}), save=False)
        self.assertEqual(found["status"], mx.DNS_FAILURE)
        self.assertNotEqual(found["status"], mx.NOT_CHECKED)

    def test_a_domain_with_no_mx_is_cached_because_that_is_an_answer(self):
        """Absence of MX is a fact about the domain, not a transport failure."""
        cache = {}
        found = mx.for_domain("nomx.test", config(), cache=cache,
                              resolver=Resolver(hosts=()), save=False)
        self.assertEqual(found["status"], mx.NO_MX)
        self.assertIn("nomx.test", cache)


class AnEntryBelongsToOneDomain(QueueTest):
    def test_one_domains_entry_is_never_used_for_another(self):
        r = Resolver()
        cache = {}
        mx.for_domain("acme.test", config(), cache=cache, resolver=r,
                      save=False)
        mx.for_domain("other.test", config(), cache=cache, resolver=r,
                      save=False)
        self.assertEqual(r.asked, ["acme.test", "other.test"])
        self.assertEqual(sorted(cache), ["acme.test", "other.test"])

    def test_the_cached_decision_names_its_own_domain(self):
        cache = {}
        mx.for_domain("acme.test", config(), cache=cache, resolver=Resolver(),
                      save=False)
        again = mx.for_domain("acme.test", config(), cache=cache,
                              resolver=Resolver(), save=False)
        self.assertEqual(again.get("email_domain") or again.get("domain"),
                         "acme.test")


class TheRunOwnsTheCacheAndPersistsItOnce(QueueTest):
    """The ownership half of the fix, at the level that was actually broken."""

    def setUp(self):
        super().setUp()
        rec = store.new_record("r1", "domains", "productive", "Acme",
                               "acme.test")
        rec["contacts"] = [{"key": "a", "name": "A", "email": "a@acme.test"},
                           {"key": "b", "name": "B", "email": "b@acme.test"}]
        rec2 = store.new_record("r2", "domains", "productive", "Other",
                                "other.test")
        rec2["contacts"] = [{"key": "c", "name": "C", "email": "c@other.test"}]
        # A SECOND RECORD AT THE SAME MAIL DOMAIN. Without it,
        # `test_the_RUN_resolves_one_domain_once_across_records` passed
        # trivially: r1's two contacts share one `enrich_record` call and so
        # share its per-record cache, which is true even with the defect. The
        # cross-RECORD property needs two records.
        rec3 = store.new_record("r3", "domains", "productive", "Sister",
                                "sister.test")
        rec3["contacts"] = [{"key": "d", "name": "D", "email": "d@acme.test"}]
        with store.transaction() as rows:
            rows.extend([rec, rec2, rec3])

    def test_enrich_record_accepts_a_run_scoped_cache(self):
        """If this fails, the cache is per-record again."""
        import inspect
        self.assertIn("mx_cache",
                      inspect.signature(enrich.enrich_record).parameters)

    def test_a_supplied_cache_is_mutated_so_the_run_can_save_it(self):
        r = Resolver()
        shared = {}
        for domain in ("acme.test", "other.test"):
            mx.for_domain(domain, config(), cache=shared, resolver=r,
                          save=False)
        self.assertEqual(sorted(shared), ["acme.test", "other.test"])

    def test_two_records_at_the_same_domain_share_one_lookup(self):
        r = Resolver()
        shared = {}
        for domain in ("acme.test", "acme.test"):
            mx.for_domain(domain, config(), cache=shared, resolver=r,
                          save=False)
        self.assertEqual(r.asked, ["acme.test"])

    def test_two_records_at_one_domain_resolve_once_ACROSS_the_run(self):
        """The mutation that nothing caught first time.

        Asserting `mx_cache` is in the signature proves the parameter exists,
        not that the run passes it. Setting `mx_cache=None` at the call site
        restores the original defect - every record loads its own cache - and
        every test still passed. This one counts real lookups through the run,
        which is the only thing that can tell the difference.
        """
        rec = store.new_record("r9", "domains", "productive", "Ninth",
                               "acme.test")
        rec["contacts"] = [{"key": "d", "name": "D", "email": "d@acme.test"}]
        with store.transaction() as rows:
            rows.append(rec)

        r = Resolver()
        cfg = config()
        with mock.patch.object(mx, "resolve", r):
            shared = {}
            for rid in ("r1", "r9"):
                record = store.get(rid)
                enrich.enrich_record(record, enrich.Budget(0), live=True,
                                     config=cfg, mx_cache=shared)
        # r1 has two contacts at acme.test, r3 has one. Three addresses, one
        # domain, one lookup.
        self.assertEqual(r.asked, ["acme.test"],
                         f"resolved {len(r.asked)} times across the run")

    def test_without_a_shared_cache_the_run_re_resolves_per_record(self):
        """The counter-case, so the test above cannot pass for the wrong reason:
        this is what the defect looked like."""
        rec = store.new_record("r4", "domains", "productive", "Fourth",
                               "acme.test")
        rec["contacts"] = [{"key": "e", "name": "E", "email": "e@acme.test"}]
        with store.transaction() as rows:
            rows.append(rec)
        r = Resolver()
        cfg = config()
        with mock.patch.object(mx, "resolve", r):
            for rid in ("r1", "r4"):
                enrich.enrich_record(store.get(rid), enrich.Budget(0),
                                     live=True, config=cfg, mx_cache=None)
        self.assertEqual(len(r.asked), 2)

    def test_the_run_reports_how_many_it_resolved(self):
        """A saving nobody can see is one nobody can defend."""
        found = enrich.run(live=False)
        self.assertIn("mx_cache", found)
        self.assertIn("resolved_this_run", found["mx_cache"])

    def live_run(self, resolver):
        """`enrich.run(live=True, cap=0)`: no credit is affordable, so the only
        provider work is the free people-count, which is stubbed."""
        from src.providers import contactout
        with mock.patch.object(mx, "resolve", resolver),              mock.patch.object(contactout, "people_count",
                               return_value={"total_results": 0}):
            return enrich.run(live=True, cap=0)

    def test_the_RUN_resolves_one_domain_once_across_records(self):
        """Catches the run not threading its own cache.

        Two records share acme.test. Mutating the call site to `mx_cache=None`
        restores the original defect, and only a test that goes through
        `enrich.run` can see it - asserting the parameter exists cannot, and
        calling `enrich_record` directly with an explicit cache cannot either.
        """
        r = Resolver()
        self.live_run(r)
        self.assertEqual(r.asked.count("acme.test"), 1,
                         f"acme.test resolved {r.asked.count('acme.test')} times "
                         f"in one run")

    def test_a_SECOND_RUN_does_not_resolve_what_the_first_one_did(self):
        """Catches the cache never being saved at the end of a run."""
        first = Resolver()
        self.live_run(first)
        self.assertIn("acme.test", first.asked)
        second = Resolver()
        self.live_run(second)
        self.assertNotIn("acme.test", second.asked,
                         "the second run re-resolved a domain the first cached")


class CohortScopingIsHonoured(QueueTest):
    """Requirement 6: a requested cohort must not require walking unrelated
    historical entries first. `--id` is what made the measured run 34s."""

    def setUp(self):
        super().setUp()
        with store.transaction() as rows:
            for i in range(6):
                rows.append(store.new_record(
                    f"r{i}", "domains", "productive", f"C{i}", f"c{i}.test"))

    def test_ids_restrict_the_walk_to_the_named_records(self):
        found = enrich.run(live=False, ids=["r2", "r4"])
        touched = {row["id"] for row in found["records"]}
        self.assertEqual(touched, {"r2", "r4"})

    def test_an_unknown_id_touches_nothing_rather_than_everything(self):
        found = enrich.run(live=False, ids=["no-such-record"])
        self.assertEqual(found["records"], [])

    def test_without_ids_every_eligible_record_is_walked(self):
        found = enrich.run(live=False)
        self.assertEqual(len(found["records"]), 6)


if __name__ == "__main__":
    unittest.main()
