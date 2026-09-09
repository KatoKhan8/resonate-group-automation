"""Stating who a client sells to, without editing a YAML file.

The readiness checklist has always pointed at `/settings` for "ICP
configured". `/settings` could not configure it. So the first batch for a
new workspace was blocked on somebody with filesystem access, and the
screen that said what was missing was also the screen that could not fix
it.

Two things make this safe to put behind a form.

**Every one of these narrows.** `must` is the sentence qualification is
scored against, the geo lists exclude, the minimum excludes. Nothing here
can make somebody contactable who was not already - verification,
suppression, hygiene and approval all sit downstream of qualification and
none of them is on this screen.

**It reaches the engine, not just the screen.** `clients.load` applies
workspace settings, so a market rule typed into a form is the same rule a
`--client` command line reads. That is asserted here on the flags a
qualification run actually produces, rather than on the value coming back
out of the store.
"""
import os
import shutil
import tempfile
import unittest

from src import clients, personas, store, workspaces as ws

ENV = ("QUEUE", "CAMPAIGNS", "WORKSPACES", "AUDIT", "CLIENTS_DIR")


class Estate(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-icp-")
        self._env = {k: os.environ.get(k) for k in ENV}
        work = os.path.join(self.tmp, "work")
        os.makedirs(work, exist_ok=True)
        os.environ["QUEUE"] = os.path.join(work, "queue.jsonl")
        os.environ["CAMPAIGNS"] = os.path.join(work, "campaigns.jsonl")
        os.environ["WORKSPACES"] = os.path.join(work, "workspaces.jsonl")
        os.environ["AUDIT"] = os.path.join(work, "audit.jsonl")
        os.environ["CLIENTS_DIR"] = os.path.join(self.tmp, "clients")
        clients.create("acme", "Acme", "acme.test")
        ws.ensure("acme", "Acme", client="acme")
        ws.add_user("root@resonate.test", "Root", super_admin=True)

    def tearDown(self):
        for key, value in self._env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        shutil.rmtree(self.tmp, ignore_errors=True)

    def set(self, **values):
        ws.set_policy("acme", values, actor="test")

    def market(self):
        return clients.load("acme").get("market") or {}


class TheMarketRule(Estate):

    def test_the_starter_states_nothing(self):
        """Missing, and reported as missing. A placeholder ICP is one that
        gets used to choose real people."""
        self.assertEqual(self.market(), {})

    def test_a_sentence_typed_into_the_form_is_what_is_in_force(self):
        self.set(**{"market.must": "services business that tracks time"})
        self.assertEqual(self.market()["must"],
                         "services business that tracks time")

    def test_a_market_list_is_read_the_way_it_is_typed(self):
        self.set(**{"market.geos": "United Kingdom, Ireland , Germany"})
        self.assertEqual(self.market()["geos"],
                         ["United Kingdom", "Ireland", "Germany"])

    def test_an_empty_list_and_no_rule_are_the_same_thing(self):
        """They behave identically to every reader, so keeping both would
        be two spellings of one state."""
        self.set(**{"market.geos": "United Kingdom"})
        self.set(**{"market.geos": "  ,  , "})
        self.assertNotIn("geos", self.market())

    def test_a_list_that_is_too_long_is_refused_rather_than_trimmed(self):
        with self.assertRaises(ws.NotOverridable):
            self.set(**{"market.geos": ",".join(str(n) for n in range(60))})

    def test_one_absurd_entry_refuses_the_whole_list(self):
        """All or nothing: a half-applied ICP is targeting nobody chose."""
        with self.assertRaises(ws.NotOverridable):
            self.set(**{"market.geos": "Ireland, " + "x" * 200})
        self.assertNotIn("geos", self.market())

    def test_the_out_of_market_answer_is_a_real_boolean(self):
        """`personas.apply_icp` compares it with `is False`. A string
        "false" is true, and would drop every flagged company."""
        self.set(**{"market.flag_dont_drop": "dropped"})
        self.assertIs(self.market()["flag_dont_drop"], False)
        self.set(**{"market.flag_dont_drop": "flagged"})
        self.assertIs(self.market()["flag_dont_drop"], True)

    def test_a_word_nobody_defined_is_refused(self):
        with self.assertRaises(ws.NotOverridable):
            self.set(**{"market.flag_dont_drop": "maybe"})

    def test_a_setting_nobody_put_on_the_list_is_still_refused(self):
        """The allowlist is the guard. A form must not be able to write an
        arbitrary key into a client's config."""
        with self.assertRaises(ws.NotOverridable):
            self.set(**{"market.anything_else": "yes"})
        with self.assertRaises(ws.NotOverridable):
            self.set(**{"verification.required_confirmations_actually": "1"})


class ItReachesQualification(Estate):
    """Asserted on what a qualification run does, not on the stored value."""

    def record(self, employees=40, country="India"):
        """Where a company is comes from the trimmed facts, which is what
        `personas.places_of` reads."""
        rec = store.new_record("x", "cold", "acme", "X Ltd", "x.test")
        rec["company_facts"] = {"employees": employees, "country": country}
        return rec

    def flags(self, rec):
        return personas.icp_flags(rec, clients.load("acme"))

    def test_with_no_rule_nothing_is_flagged(self):
        self.assertEqual(self.flags(self.record()), [])

    def test_an_excluded_market_is_flagged(self):
        self.set(**{"market.exclude_geos": "India"})
        self.assertIn("geo excluded by client: India",
                      self.flags(self.record()))

    def test_a_company_outside_the_stated_markets_is_flagged(self):
        self.set(**{"market.geos": "United Kingdom, Ireland"})
        self.assertIn("geo outside client's stated markets",
                      self.flags(self.record()))

    def test_a_company_inside_them_is_not(self):
        self.set(**{"market.geos": "United Kingdom, India"})
        self.assertEqual([f for f in self.flags(self.record())
                          if "stated markets" in f], [])

    def test_the_minimum_size_is_applied(self):
        self.set(**{"market.size_min_employees": "50"})
        self.assertIn("under the client minimum of 50",
                      " ".join(self.flags(self.record(employees=40))))

    def test_flagged_does_not_drop_the_record(self):
        self.set(**{"market.exclude_geos": "India"})
        rec = self.record()
        personas.apply_icp(rec, clients.load("acme"))
        self.assertNotEqual(rec.get("state"), "dropped")

    def test_dropped_does(self):
        self.set(**{"market.exclude_geos": "India",
                    "market.flag_dont_drop": "dropped"})
        rec = self.record()
        personas.apply_icp(rec, clients.load("acme"))
        self.assertEqual(rec.get("state"), "dropped")


class WhatTheChecklistSays(Estate):

    def steps(self):
        from src import repo as repo_module
        from src.web import api

        repo = repo_module.Repo.for_user("root@resonate.test", "acme")
        return {s["key"]: s for s in api.onboarding(repo)["steps"]}

    def test_it_starts_outstanding(self):
        self.assertFalse(self.steps()["icp"]["done"])

    def test_filling_the_form_completes_it(self):
        """The checklist has always pointed at `/settings` for this. Until
        now `/settings` could not do it."""
        self.set(**{"market.must": "services business that tracks time"})
        step = self.steps()["icp"]
        self.assertTrue(step["done"])
        self.assertIn("/settings", step["where"])

    def test_personas_are_still_outstanding_and_still_say_so(self):
        """The half this does not close. A checklist that went green while
        a workspace had no personas would be the worse defect."""
        self.set(**{"market.must": "services business that tracks time"})
        self.assertFalse(self.steps()["personas"]["done"])


class OnTheScreen(Estate):

    def view(self):
        from src import repo as repo_module
        from src.web import api

        repo = repo_module.Repo.for_user("root@resonate.test", "acme")
        return api.workspace_settings(repo)

    def field(self, key):
        return next(f for f in self.view()["editable"] if f["key"] == key)

    def test_every_market_setting_is_offered(self):
        offered = {f["key"] for f in self.view()["editable"]
                   if f["key"].startswith("market.")}
        self.assertEqual(offered, {"market.must", "market.size_min_employees",
                                   "market.geos", "market.exclude_geos",
                                   "market.flag_dont_drop"})

    def test_a_list_renders_the_way_it_is_typed(self):
        from src.web import pages

        self.set(**{"market.geos": "United Kingdom, Ireland"})
        html = pages._policy_field(self.field("market.geos"))
        self.assertIn("United Kingdom, Ireland", html)

    def test_the_boolean_renders_as_words_rather_than_a_tick(self):
        from src.web import pages

        self.set(**{"market.flag_dont_drop": "dropped"})
        html = pages._policy_field(self.field("market.flag_dont_drop"))
        self.assertIn("dropped", html)
        self.assertIn("selected", html)

    def test_the_settings_page_groups_them_under_one_heading(self):
        from src.web import pages

        html = pages.workspace_settings(self.view(), False, "csrf")
        self.assertIn("Who this client sells to", html)
        self.assertIn("policy:market.must", html)


if __name__ == "__main__":
    unittest.main()
