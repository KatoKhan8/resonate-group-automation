"""Saying who a decision maker is, without editing a YAML file.

The readiness checklist has always had a "personas configured" step and it
pointed at a screen that could not configure them. So the second thing
blocking a new workspace's first batch was the same as the first: somebody
with filesystem access.

This is the one settings surface that changes who gets *selected*, which is
more than the rest of them do, so the tests are mostly about what it may
not do.

**A persona that can never select anybody is refused.** An empty title list
is not a persona, it is a batch that comes back with nobody in it and no
explanation. Refusing at the form is the only place a person is looking.

**An override replaces, and says so.** Half a persona set from a form and
half from a file is a targeting rule nobody can read in one place. The
screen names which of the two is in force.

**Selecting is not contacting.** The cap bounds fan-out per company, and
qualification, verification, email security, engagement history,
suppression, pacing and approval all sit after selection and are untouched
by anything here. The last test in this file is the one that says so about
real state rather than in a comment.
"""
import os
import shutil
import tempfile
import unittest

from src import clients, personas as persona_model, store, workspaces as ws

ENV = ("QUEUE", "CAMPAIGNS", "WORKSPACES", "AUDIT", "CLIENTS_DIR")

CHAMPION = {"titles": "Operations Manager, Head of Operations",
            "cap": "2", "angles": "ops: utilisation and capacity planning"}


class Estate(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-persona-")
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

    def repo(self, email="root@resonate.test"):
        from src import repo as repo_module
        return repo_module.Repo.for_user(email, "acme")

    def save(self, name="champion", **kw):
        from src.web import api
        fields = dict(CHAMPION, **kw)
        return api.save_persona(self.repo(), name, fields["titles"],
                                fields["cap"], fields["angles"],
                                by="root@resonate.test")

    def view(self):
        from src.web import api
        return api.personas_view(self.repo())

    def stored(self):
        return clients.load("acme").get("personas") or {}


class WhatCanBeSaved(Estate):

    def test_the_starter_has_none(self):
        self.assertEqual(self.stored(), {})
        self.assertEqual(self.view()["personas"], [])

    def test_one_persona_saved_is_one_persona_in_force(self):
        self.save()
        found = self.stored()["champion"]
        self.assertEqual(found["titles"],
                         ["Operations Manager", "Head of Operations"])
        self.assertEqual(found["cap_per_domain"], 2)
        self.assertEqual(found["angles"],
                         {"ops": "utilisation and capacity planning"})

    def test_a_second_persona_joins_rather_than_replacing(self):
        self.save()
        self.save("economic_buyer", titles="CFO, COO", cap="1", angles="")
        self.assertEqual(sorted(self.stored()), ["champion", "economic_buyer"])

    def test_saving_the_same_name_replaces_that_one_only(self):
        self.save()
        self.save("economic_buyer", titles="CFO", cap="1", angles="")
        self.save(titles="Operations Director", cap="1", angles="")
        self.assertEqual(self.stored()["champion"]["titles"],
                         ["Operations Director"])
        self.assertEqual(self.stored()["economic_buyer"]["titles"], ["CFO"])

    def test_a_persona_with_no_titles_is_refused(self):
        """It can never select anybody, and nobody would find that out
        until a batch came back empty."""
        with self.assertRaises(ws.NotOverridable):
            self.save(titles="  ,  ")
        self.assertEqual(self.stored(), {})

    def test_a_name_that_is_not_a_key_is_refused(self):
        for bad in ("1champion", "Champion Person", "champion!", "", "  "):
            with self.subTest(name=bad):
                with self.assertRaises(ws.NotOverridable):
                    self.save(bad)

    def test_a_name_is_lower_cased_rather_than_refused(self):
        """Somebody typing `Champion` means `champion`, and two personas
        differing only in case are one persona with a typo."""
        self.save("Champion")
        self.assertEqual(sorted(self.stored()), ["champion"])

    def test_the_cap_has_bounds_and_they_are_enforced(self):
        for bad in ("0", "-1", "99", "two"):
            with self.subTest(cap=bad):
                with self.assertRaises(ws.NotOverridable):
                    self.save(cap=bad)

    def test_a_blank_cap_is_the_most_conservative_one(self):
        """One person per company. A blank field must not become "as many
        as match", which is the direction this is allowed to fail in."""
        self.save(cap="")
        self.assertEqual(self.stored()["champion"]["cap_per_domain"], 1)

    def test_an_angle_needs_a_name_and_something_to_say(self):
        with self.assertRaises(ws.NotOverridable):
            self.save(angles="just a sentence with no name")
        with self.assertRaises(ws.NotOverridable):
            self.save(angles="ops:")

    def test_angles_are_optional(self):
        self.save(angles="")
        self.assertNotIn("angles", self.stored()["champion"])
        self.assertTrue(self.view()["personas"][0]["no_angles"])

    def test_removing_the_last_one_puts_the_file_back_in_charge(self):
        """Rather than leaving the workspace with a persona set of nobody."""
        self.save()
        from src.web import api
        api.remove_persona(self.repo(), "champion", by="root@resonate.test")
        self.assertEqual(self.stored(), {})
        self.assertNotIn("personas", ws.policy("acme"))

    def test_removing_one_that_is_not_there_changes_nothing(self):
        from src.web import api
        self.save()
        self.assertIsNone(api.remove_persona(self.repo(), "nobody"))
        self.assertEqual(sorted(self.stored()), ["champion"])

    def test_the_change_is_in_the_audit_log(self):
        self.save()
        actions = [row.get("action") for row in ws.audit("acme")]
        self.assertIn("workspace.policy_changed", actions)


class WhereItCameFrom(Estate):

    def test_before_an_edit_the_file_is_in_charge(self):
        view = self.view()
        self.assertFalse(view["overridden"])
        self.assertEqual(view["source"], "the client file")

    def test_after_an_edit_this_workspace_is(self):
        self.save()
        view = self.view()
        self.assertTrue(view["overridden"])
        self.assertEqual(view["source"], "this workspace")

    def test_the_first_edit_starts_from_what_the_file_says(self):
        """A workspace still running on its client file must not have that
        file's personas wiped by adding one of its own."""
        with open(clients.path_for("acme"), "a", encoding="utf-8",
                  newline="\n") as handle:
            handle.write("personas:\n  economic_buyer:\n"
                         "    titles: [CFO, COO]\n    cap_per_domain: 1\n")
        self.assertEqual(sorted(self.stored()), ["economic_buyer"])
        self.save()
        self.assertEqual(sorted(self.stored()),
                         ["champion", "economic_buyer"])


class ItReachesSelection(Estate):
    """Asserted on who a selection run actually keeps."""

    def record(self):
        rec = store.new_record("x", "domains", "acme", "X Ltd", "x.test")
        rec["contacts"] = [
            {"key": "a", "name": "A Person", "title": "Operations Manager",
             "email": "a@x.test"},
            {"key": "b", "name": "B Person", "title": "Head of Operations",
             "email": "b@x.test"},
            {"key": "c", "name": "C Person", "title": "Operations Director",
             "email": "c@x.test"},
            {"key": "d", "name": "D Person", "title": "Warehouse Picker",
             "email": "d@x.test"},
        ]
        return rec

    def kept(self, rec):
        keep, _ = persona_model.select_domains(rec, clients.load("acme"))
        return sorted(c["key"] for c in keep)

    def test_with_no_personas_nobody_is_selected(self):
        self.assertEqual(self.kept(self.record()), [])

    def test_a_saved_persona_selects_the_people_who_match_it(self):
        self.save()
        self.assertEqual(self.kept(self.record()), ["a", "b"])

    def test_the_cap_is_what_bounds_the_fan_out(self):
        self.save(titles="Operations Manager, Head of Operations, "
                         "Operations Director", cap="1")
        self.assertEqual(len(self.kept(self.record())), 1)

    def test_somebody_matching_nothing_is_still_not_selected(self):
        self.save(titles="Operations Manager, Head of Operations, "
                         "Operations Director", cap="3")
        self.assertNotIn("d", self.kept(self.record()))

    def test_the_angle_is_assigned_when_there_is_only_one(self):
        self.save()
        rec = self.record()
        persona_model.select_domains(rec, clients.load("acme"))
        chosen = next(c for c in rec["contacts"] if c["key"] == "a")
        self.assertEqual(chosen["angle"], "ops")

    def test_with_no_angle_selection_still_works(self):
        """A persona with no angle selects people; what it cannot do is say
        anything specific to them. That is a degradation, not a failure."""
        self.save(angles="")
        rec = self.record()
        keep, _ = persona_model.select_domains(rec, clients.load("acme"))
        self.assertTrue(keep)
        self.assertIsNone(keep[0].get("angle"))

    def test_a_command_line_reads_the_same_personas(self):
        """`clients.load` applies workspace settings, so the form and the
        batch agree. That is the property the whole screen rests on."""
        self.save()
        rec = self.record()
        store.save([rec])
        result = persona_model.run(apply=True, ids=["x"])
        kept = [c["key"] for c in result["records"][0]["kept"]]
        self.assertEqual(sorted(kept), ["a", "b"])


class WhatItDoesNotTouch(Estate):
    """Selecting somebody is not contacting them."""

    def test_a_selected_contact_is_not_sendable_on_that_account(self):
        from src import lint

        self.save()
        rec = store.new_record("x", "domains", "acme", "X Ltd", "x.test")
        rec["contacts"] = [{"key": "a", "name": "A Person",
                            "title": "Operations Manager",
                            "email": "a@x.test"}]
        persona_model.select_domains(rec, clients.load("acme"))
        self.assertTrue(rec["contacts"][0].get("persona"))
        self.assertFalse(lint.sendable(rec["contacts"][0]),
                         "an unverified address became sendable by being "
                         "chosen as a persona")

    def test_the_verification_rule_is_not_on_this_screen(self):
        """Anything that could weaken it would have to be an overridable
        key, and the allowlist is the guard."""
        for key in ws.POLICY_KEYS:
            if key.startswith("personas") or key.startswith("market."):
                with self.subTest(key=key):
                    self.assertNotIn("verification", key)


class OnTheScreen(Estate):

    def html(self, **kw):
        from src.web import pages
        return pages.workspace_personas(self.view(), "csrf", **kw)

    def test_an_empty_set_says_what_that_means(self):
        self.assertIn("would select nobody", self.html())

    def test_a_saved_persona_is_listed_with_its_cap(self):
        self.save()
        html = self.html()
        self.assertIn("champion", html)
        self.assertIn("Operations Manager", html)
        self.assertIn("utilisation and capacity planning", html)

    def test_a_persona_with_no_angle_says_what_happens_instead(self):
        self.save(angles="")
        self.assertIn("falls back to general wording", self.html())

    def test_it_says_which_of_the_two_is_in_force(self):
        self.assertIn("the client file", self.html())
        self.save()
        self.assertIn("this workspace", self.html())

    def test_a_refusal_is_shown_on_the_page_rather_than_swallowed(self):
        self.assertIn("needs at least one title",
                      self.html(error="champion needs at least one title"))

    def test_a_role_that_may_not_manage_gets_no_form(self):
        from src.web import api

        ws.add_user("ops@acme.test", "Ops")
        ws.save(ws.load() + [ws.new_membership("ops@acme.test", "acme",
                                               "operator")])
        from src import repo as repo_module
        from src.web import pages
        view = api.personas_view(
            repo_module.Repo.for_user("ops@acme.test", "acme"))
        self.assertFalse(view["can_manage"])
        self.assertNotIn("Save persona",
                         pages.workspace_personas(view, "csrf"))


if __name__ == "__main__":
    unittest.main()
