"""Personas, contact identity and the domains lane. BUILD-SPEC phase 6.

Acceptance test, section 10: one domain in, capped persona set out, collisions
in `excluded`.

No provider is called anywhere in this file.
"""
import json
import os
import shutil
import tempfile
import unittest

from src import clients, identity, lint, personas, store
from tests.base import FIXTURES


class PersonaTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-personas-")
        self.queue = os.path.join(self.tmp, "work", "queue.jsonl")
        self.out = os.path.join(self.tmp, "out")
        os.makedirs(os.path.dirname(self.queue), exist_ok=True)
        shutil.copyfile(os.path.join(FIXTURES, "phase6.jsonl"), self.queue)
        self._prev = os.environ.get("QUEUE"), os.environ.get("OUT")
        os.environ["QUEUE"], os.environ["OUT"] = self.queue, self.out

    def tearDown(self):
        for name, value in zip(("QUEUE", "OUT"), self._prev):
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        shutil.rmtree(self.tmp, ignore_errors=True)

    def rec(self, rid):
        return store.get(rid)


class TestTheAcceptanceTest(PersonaTest):
    """One domain in, capped persona set out, collisions in excluded."""

    def setUp(self):
        super().setUp()
        personas.run(apply=True, do_export=True, ids=["meridian"])
        self.meridian = self.rec("meridian")

    def test_the_persona_set_is_capped_per_the_client_config(self):
        config = clients.load("productive")
        kept = self.meridian["contacts"]
        champions = [c for c in kept if c["persona"] == "champion"]
        buyers = [c for c in kept if c["persona"] == "economic_buyer"]
        self.assertEqual(len(champions), clients.cap_for(config, "champion"))
        self.assertEqual(len(buyers), clients.cap_for(config, "economic_buyer"))
        self.assertEqual(len(kept), 3)

    def test_every_kept_contact_has_a_persona(self):
        for c in self.meridian["contacts"]:
            self.assertTrue(c["persona"], c["name"])

    def test_the_over_cap_contact_is_excluded_with_a_reason(self):
        reasons = {e["name"]: e["why"] for e in self.meridian["excluded"]}
        self.assertIn("over the cap", reasons.get("Petra Jelić", ""))

    def test_a_non_persona_title_is_excluded_with_a_reason(self):
        reasons = {e["name"]: e["why"] for e in self.meridian["excluded"]}
        self.assertEqual(reasons.get("Tomislav Barić"), "not a persona for this client")

    def test_the_collision_from_enrichment_is_still_in_excluded(self):
        """Section 9, trap 1: what was thrown away stays visible."""
        reasons = {e["name"]: e["why"] for e in self.meridian["excluded"]}
        self.assertIn("collision", reasons.get("Luc Marchand", ""))

    def test_the_per_domain_folder_is_written(self):
        path = os.path.join(self.out, "domains", "meridian.test")
        for name in ("company.json", "people.json", "people.csv", "cadence.json"):
            self.assertTrue(os.path.exists(os.path.join(path, name)), name)

    def test_the_export_carries_personas_angles_and_the_excluded(self):
        path = os.path.join(self.out, "domains", "meridian.test")
        with open(os.path.join(path, "people.json"), encoding="utf-8") as f:
            people = json.load(f)
        self.assertEqual(len(people["people"]), 3)
        self.assertTrue(all(p["persona"] for p in people["people"]))
        self.assertTrue(any("collision" in e["why"] for e in people["excluded"]))
        with open(os.path.join(path, "company.json"), encoding="utf-8") as f:
            self.assertEqual(json.load(f)["employees"], 26)


class TestContactIdentity(unittest.TestCase):
    def test_croatian_diacritics_transliterate_rather_than_vanish(self):
        self.assertEqual(identity.base_key({"name": "Ćuk Šimić"}), "cuk-simic")
        self.assertEqual(identity.base_key({"name": "Ivana Šarić"}), "ivana-saric")
        self.assertEqual(identity.base_key({"name": "Đorđe Žarković"}), "dorde-zarkovic")

    def test_a_fully_non_latin_name_still_gets_a_stable_id(self):
        person = {"name": "梁伟", "email": "wei.liang@example.test"}
        key = identity.base_key(person)
        self.assertEqual(key, "wei-liang")
        self.assertEqual(key, identity.base_key(dict(person)))

    def test_a_name_with_nothing_usable_falls_back_to_a_hash(self):
        person = {"name": "梁伟", "linkedin": "https://www.linkedin.com/in/wei"}
        key = identity.base_key(person)
        self.assertTrue(key.startswith("contact-"), key)
        self.assertEqual(key, identity.base_key(dict(person)))

    def test_two_names_that_would_collide_stay_distinct(self):
        a = {"name": "Ana Marić", "email": "ana.maric@example.test"}
        b = {"name": "Ana Maric", "email": "ana.maric2@example.test"}
        identity.assign_keys([a, b])
        self.assertNotEqual(a["key"], b["key"])
        self.assertEqual(a["key"], "ana-maric")
        self.assertTrue(b["key"].startswith("ana-maric-"))

    def test_collision_ids_are_stable_across_re_runs(self):
        def keys():
            a = {"name": "Ana Marić", "email": "ana.maric@example.test"}
            b = {"name": "Ana Maric", "email": "ana.maric2@example.test"}
            identity.assign_keys([a, b])
            return a["key"], b["key"]
        self.assertEqual(keys(), keys())

    def test_the_same_person_in_two_records_gets_the_same_id(self):
        person = {"name": "Ivana Šarić", "email": "ivana.saric@meridian.test"}
        one, two = dict(person), dict(person)
        identity.assign_keys([one])
        identity.assign_keys([two])
        self.assertEqual(one["key"], two["key"])

    def test_a_stored_key_is_never_rewritten(self):
        person = {"name": "Ivana Šarić", "key": "legacy-key-from-an-earlier-run"}
        identity.assign_keys([person])
        self.assertEqual(person["key"], "legacy-key-from-an-earlier-run")

    def test_record_ids_are_untouched_by_all_of_this(self):
        """Phase 1 slugs must not move: they are already committed to the queue."""
        from src import ingest
        self.assertEqual(ingest.slug("Meridian"), "meridian")
        self.assertEqual(ingest.slug("BrightPath Leads"), "brightpath-leads")
        self.assertEqual(ingest.slug("Ivana Šarić"), "ivana-ari")

    def test_lint_resolves_a_stored_key(self):
        rec = {"contacts": [{"name": "Ćuk Šimić", "key": "cuk-simic",
                             "email": "c@example.test", "verdict": "valid"}]}
        self.assertIsNotNone(lint.find_contact(rec, "cuk-simic"))

    def test_lint_still_resolves_a_record_with_no_stored_key(self):
        rec = {"contacts": [{"name": "Ivana Saric", "email": "r@example.test"}]}
        self.assertIsNotNone(lint.find_contact(rec, "ivana-saric"))


class TestLanesStaySeparate(PersonaTest):
    def test_revive_keeps_the_person_from_the_thread_without_a_persona_title(self):
        personas.run(apply=True, ids=["harbourline"])
        rec = self.rec("harbourline")
        names = [c["name"] for c in rec["contacts"]]
        self.assertIn("Jesse Hollis", names)
        self.assertEqual(rec["excluded"], [])

    def test_revive_does_not_apply_the_domains_cap(self):
        personas.run(apply=True, ids=["harbourline"])
        self.assertEqual(len(self.rec("harbourline")["contacts"]), 3)

    def test_cold_keeps_the_person_the_signal_names(self):
        personas.run(apply=True, ids=["vantage"])
        rec = self.rec("vantage")
        self.assertEqual([c["name"] for c in rec["contacts"]], ["Nikola Ferić"])

    def test_a_contact_with_no_address_or_profile_is_excluded_not_dropped(self):
        personas.run(apply=True, ids=["harbourline"])
        rec = self.rec("harbourline")
        self.assertTrue(all(c.get("email") or c.get("linkedin") for c in rec["contacts"]))

    def test_only_the_domains_lane_exports_a_folder(self):
        personas.run(apply=True, do_export=True)
        self.assertTrue(os.path.exists(os.path.join(self.out, "domains", "meridian.test")))
        self.assertFalse(os.path.exists(os.path.join(self.out, "domains", "harbourline.test")))


class TestSelectionIsDeterministic(PersonaTest):
    def test_the_same_input_selects_the_same_people_every_time(self):
        first = personas.run(ids=["meridian"])["records"][0]
        second = personas.run(ids=["meridian"])["records"][0]
        self.assertEqual(first, second)

    def test_applying_twice_changes_nothing(self):
        personas.run(apply=True, ids=["meridian"])
        with open(self.queue, "rb") as f:
            once = f.read()
        personas.run(apply=True, ids=["meridian"])
        rec = self.rec("meridian")
        self.assertEqual(len(rec["contacts"]), 3)
        self.assertEqual(len([e for e in rec["excluded"]
                              if e["name"] == "Tomislav Barić"]), 1)
        self.assertEqual(len(once.splitlines()), len(store.load()))

    def test_a_dry_run_writes_nothing(self):
        with open(self.queue, "rb") as f:
            before = f.read()
        personas.run()
        with open(self.queue, "rb") as f:
            self.assertEqual(f.read(), before)

    def test_ranking_prefers_the_better_title_match(self):
        config = clients.load("productive")
        exact = {"title": "Head of Finance", "key": "a"}
        loose = {"title": "Finance and Admin Assistant", "key": "b"}
        self.assertGreater(personas.classify(exact, config)[1],
                           personas.classify(loose, config)[1])

    def test_an_angle_is_assigned_only_when_the_persona_has_exactly_one(self):
        """The rule, asserted against a config this test owns.

        It used to read the live Productive file, where `economic_buyer`
        happened to define exactly one angle. That made a rule test depend on
        a client's copy decisions: adding a second angle - which Productive
        did, so an operations lead stops inheriting founder wording - broke a
        test about `default_angle` rather than about Productive.
        """
        one = {"personas": {"buyer": {"angles": {"founder": "a phrase"}}}}
        many = {"personas": {"buyer": {"angles": {"founder": "a", "ops": "b"}}}}
        self.assertEqual(personas.default_angle(one, "buyer"), "founder")
        self.assertIsNone(personas.default_angle(many, "buyer"))

    def test_a_matching_routing_family_picks_the_angle(self):
        """Above the single-angle rule: an operations lead is written to
        about operations rather than inheriting whatever came first."""
        many = {"personas": {"buyer": {"angles": {"founder": "a", "ops": "b"}}}}
        self.assertEqual(personas.default_angle(many, "buyer", "ops"), "ops")
        self.assertIsNone(personas.default_angle(many, "buyer", "finance"))


class TestOneBadRecordDoesNotStopTheBatch(PersonaTest):
    """Regression: a missing client config raised and aborted the whole run."""

    def test_a_record_with_no_client_config_is_skipped_not_fatal(self):
        recs = store.load()
        recs[0]["client"] = "nosuchclient"
        store.save(recs)
        result = personas.run(apply=True)
        skipped = [r for r in result["records"] if r.get("skipped")]
        self.assertEqual(len(skipped), 1)
        self.assertIn("nosuchclient", skipped[0]["skipped"])

    def test_the_other_records_are_still_processed(self):
        recs = store.load()
        recs[0]["client"] = "nosuchclient"
        store.save(recs)
        personas.run(apply=True)
        self.assertEqual([c["name"] for c in self.rec("vantage")["contacts"]],
                         ["Nikola Ferić"])


class TestIcpFlagging(PersonaTest):
    """Section 4: out of geo is flagged for a human call, not dropped."""

    def test_an_out_of_geo_company_is_flagged_and_kept(self):
        personas.run(apply=True, ids=["meridian"])
        rec = self.rec("meridian")
        self.assertIn("geo outside client's stated markets",
                      rec["company_facts"]["icp_flags"])
        self.assertEqual(rec["state"], "verified")
        self.assertIsNone(rec["drop_reason"])
        self.assertTrue(rec["contacts"])

    def test_an_in_geo_company_carries_no_geo_flag(self):
        recs = store.load()
        for r in recs:
            if r["id"] == "meridian":
                r["company_facts"]["offices"] = ["London UK", "Dublin IE"]
        store.save(recs)
        personas.run(apply=True, ids=["meridian"])
        flags = self.rec("meridian")["company_facts"].get("icp_flags", [])
        self.assertNotIn("geo outside client's stated markets", flags)

    def test_an_explicitly_excluded_geo_is_named(self):
        config = clients.load("productive")
        rec = {"company_facts": {"offices": ["Mumbai IN"], "employees": 50}}
        self.assertIn("geo excluded by client: India", personas.icp_flags(rec, config))

    def test_under_the_size_floor_is_flagged(self):
        config = clients.load("productive")
        rec = {"company_facts": {"offices": ["London UK"], "employees": 4}}
        flags = personas.icp_flags(rec, config)
        self.assertTrue(any("under the client minimum" in f for f in flags))

    def test_flag_dont_drop_false_does_drop(self):
        config = clients.load("productive")
        config["market"]["flag_dont_drop"] = False
        rec = {"id": "x", "state": "verified", "drop_reason": None, "log": [],
               "company_facts": {"offices": ["Mumbai IN"], "employees": 50}}
        personas.apply_icp(rec, config)
        self.assertEqual(rec["state"], "dropped")
        self.assertIn("India", rec["drop_reason"])

    def test_a_country_code_counts_as_the_geo(self):
        self.assertTrue(personas.mentions("london uk", "United Kingdom"))
        self.assertTrue(personas.mentions("stockholm se", "Nordics"))
        self.assertFalse(personas.mentions("zagreb hr", "United Kingdom"))

    def test_no_facts_means_no_guess(self):
        config = clients.load("productive")
        self.assertEqual(personas.icp_flags({"company_facts": {}}, config), [])


class TestExportIsReRunnable(PersonaTest):
    def test_exporting_twice_produces_identical_bytes(self):
        personas.run(apply=True, do_export=True, ids=["meridian"])
        path = os.path.join(self.out, "domains", "meridian.test")
        def snapshot():
            out = {}
            for name in sorted(os.listdir(path)):
                with open(os.path.join(path, name), "rb") as f:
                    out[name] = f.read()
            return out

        first = snapshot()
        personas.run(apply=True, do_export=True, ids=["meridian"])
        second = snapshot()
        self.assertEqual(first, second)


class TestClientConfig(unittest.TestCase):
    def test_the_real_client_file_parses(self):
        config = clients.load("productive")
        self.assertEqual(clients.cap_for(config, "champion"), 2)
        self.assertEqual(clients.cap_for(config, "economic_buyer"), 1)
        self.assertEqual(config["market"]["size_min_employees"], 20)
        self.assertIs(config["market"]["flag_dont_drop"], True)
        self.assertIn("United Kingdom", config["market"]["geos"])
        self.assertIn("India", config["market"]["exclude_geos"])
        self.assertEqual(config["personas"]["economic_buyer"]["start_offset_days"], 5)

    def test_a_wrapped_inline_list_is_read_whole(self):
        parsed = clients.parse("market:\n  geos: [United Kingdom, Ireland,\n"
                               "         Germany, France]\n")
        self.assertEqual(parsed["market"]["geos"],
                         ["United Kingdom", "Ireland", "Germany", "France"])

    def test_a_comment_is_not_data(self):
        parsed = clients.parse("cap: 2   # two per domain\nname: Productive\n")
        self.assertEqual(parsed, {"cap": 2, "name": "Productive"})

    def test_a_url_keeps_its_slashes_and_is_not_cut_at_a_hash(self):
        parsed = clients.parse("booking_link: https://example.com/get-started/\n")
        self.assertEqual(parsed["booking_link"], "https://example.com/get-started/")

    def test_unsupported_yaml_raises_rather_than_being_misread(self):
        with self.assertRaises(clients.ConfigError):
            clients.parse("geos:\n  - United Kingdom\n")

    def test_a_missing_client_raises(self):
        with self.assertRaises(clients.ConfigError):
            clients.load("nosuchclient")


if __name__ == "__main__":
    unittest.main()
