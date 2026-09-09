"""Adding a client without editing a file by hand.

Two things had to exist before this was possible and neither did: a way to
create the workspace row, and a way to write the client config. Doing either
alone leaves a state somebody discovers three screens later - a workspace
that cannot load a client, or a config file nobody owns.

The slug is the dangerous part. It becomes a filename, and nothing outside
this process could set one until now. `../../etc/passwd` is a perfectly good
dict key right up until it is joined onto a path, so the grammar is asserted
adversarially rather than assumed.

What the starter deliberately does not carry is the other half of the design.
No market, no personas: the readiness list is meant to say those are missing,
and a placeholder ICP is one that gets used to choose real people.
"""
import os
import shutil
import tempfile
import unittest

from tests.webbase import WebTest

from src import clients, workspaces as ws


class TheSlugIsAFilename(unittest.TestCase):

    def test_traversal_is_refused(self):
        for bad in ("..", "../x", "../../etc/passwd", "a/b", "a\\b",
                    "/etc/passwd", "c:", "c:/windows"):
            with self.subTest(slug=bad):
                self.assertFalse(clients.valid_slug(bad))
                with self.assertRaises(clients.ConfigError):
                    clients.path_for(bad)

    def test_windows_device_names_are_refused(self):
        """`con.yaml` is not a file on Windows, it is a device. The grammar
        alone lets these through - they look like ordinary words."""
        for bad in ("con", "prn", "aux", "nul", "com1", "lpt9"):
            with self.subTest(slug=bad):
                self.assertFalse(clients.valid_slug(bad))

    def test_the_awkward_shapes_are_refused(self):
        for bad in ("", " ", "a", "-acme", "acme.", "acme ", "Acme",
                    "acme co", "acme\x00", "x" * 41, None):
            with self.subTest(slug=bad):
                self.assertFalse(clients.valid_slug(bad))

    def test_ordinary_names_are_accepted(self):
        for good in ("acme", "acme-security", "a1", "x" * 40):
            with self.subTest(slug=good):
                self.assertTrue(clients.valid_slug(good))


class TheStarterConfig(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-onb-")
        self._previous = os.environ.get("CLIENTS_DIR")
        os.environ["CLIENTS_DIR"] = self.tmp

    def tearDown(self):
        if self._previous is None:
            os.environ.pop("CLIENTS_DIR", None)
        else:
            os.environ["CLIENTS_DIR"] = self._previous
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_it_writes_something_the_parser_can_read_back(self):
        clients.create("acme-security", "Acme Security", "acme-security.test",
                       "https://acme-security.test/book")
        config = clients.load("acme-security")
        self.assertEqual(config["name"], "Acme Security")
        self.assertEqual(config["domain"], "acme-security.test")

    def test_a_booking_link_keeps_its_colon(self):
        """A bare colon is fine in this parser and a URL needs one. Only a
        colon followed by a space ends a key."""
        clients.create("acme", "Acme", "acme.test", "https://acme.test/book")
        self.assertEqual(clients.load("acme")["booking_link"],
                         "https://acme.test/book")

    def test_it_carries_no_icp_and_no_personas(self):
        """The readiness list has to be able to say these are missing."""
        clients.create("acme", "Acme", "acme.test")
        config = clients.load("acme")
        self.assertNotIn("market", config)
        self.assertEqual(config["personas"], {})

    def test_it_says_nothing_about_verification_or_sending(self):
        """Those are policy with safe defaults in code. A per-client file
        that could restate them is one that could weaken them."""
        body = open(clients.path_for("acme") if clients.exists("acme")
                    else clients.create("acme", "Acme", "acme.test"),
                    encoding="utf-8").read().lower()
        for forbidden in ("verification", "required_confirmations",
                          "live_sending", "approval"):
            self.assertNotIn(forbidden, body)

    def test_a_name_cannot_inject_structure(self):
        """The name is somebody's typing. It must not be able to add a key.

        What protects this is collapsing whitespace: a value that cannot
        reach a second line cannot become a second key, whatever colons it
        carries. Asserted on the file as well as on the parse, because a
        parser that grew stricter later should still be handed one line -
        and because asserting only the parse let a redundant colon-strip
        look load-bearing when it was not.
        """
        clients.create("evil-co", "Evil: name\nmarket:\n  must: anything",
                       "evil.test")
        config = clients.load("evil-co")
        self.assertNotIn("market", config)
        self.assertEqual(sorted(config),
                         ["booking_link", "cadence", "domain", "name",
                          "personas", "sender", "tone"])

        # Asserted on keys, not on the word: the starter's own comment says
        # "fill in the market and personas", so searching the text for
        # "market" finds the instruction rather than an injection.
        body = open(clients.path_for("evil-co"), encoding="utf-8").read()
        lines = [l for l in body.splitlines() if not l.lstrip().startswith("#")]
        self.assertEqual(len([l for l in lines if l.startswith("name:")]), 1)
        keys = {l.split(":", 1)[0].strip() for l in lines if ":" in l}
        self.assertNotIn("market", keys)
        self.assertNotIn("must", keys)

    def test_it_never_overwrites(self):
        """A client's ICP is somebody's real targeting. A create that
        replaced one would be the most expensive convenience here."""
        clients.create("acme", "Acme", "acme.test")
        with self.assertRaises(clients.ConfigError):
            clients.create("acme", "Somebody Else", "other.test")
        self.assertEqual(clients.load("acme")["name"], "Acme")

    def test_a_nameless_client_is_refused(self):
        with self.assertRaises(clients.ConfigError):
            clients.create("acme", "   ", "acme.test")


class CreatingAWorkspace(WebTest):

    def create(self, slug="acme-security", name="Acme Security",
               domain="acme-security.test", by="root@resonate.test"):
        from src.web import api
        return api.create_workspace(slug, name, domain, by=by)

    def cleanup(self, slug):
        rows = [r for r in ws.load() if r.get("slug") != slug]
        ws.save(rows)
        if clients.exists(slug):
            os.remove(clients.path_for(slug))

    def test_the_workspace_and_the_config_arrive_together(self):
        try:
            entry = self.create()
            self.assertEqual(entry["slug"], "acme-security")
            self.assertTrue(clients.exists("acme-security"))
            self.assertIsNotNone(ws.workspace("acme-security"))
        finally:
            self.cleanup("acme-security")

    def test_an_existing_workspace_is_refused(self):
        from src.web import api
        with self.assertRaises(api.WorkspaceRefused):
            self.create(slug="productive")

    def test_an_orphan_config_blocks_reuse_of_the_name(self):
        """A file with no workspace means the name belonged to somebody."""
        from src.web import api
        clients.create("ghost-co", "Ghost", "ghost.test")
        try:
            with self.assertRaises(api.WorkspaceRefused):
                self.create(slug="ghost-co")
        finally:
            self.cleanup("ghost-co")

    def test_a_bad_slug_never_reaches_the_filesystem(self):
        """Asserted as "no new file", not as "the directory is unchanged" -
        the estate's own configs are none of this test's business."""
        from src.web import api
        before = set(os.listdir(clients.clients_dir()))
        for bad in ("../evil", "a/b", "..", "/etc/passwd", "con", "nul",
                    "com1", "a", "x" * 41, "acme.", "acme co"):
            with self.subTest(slug=bad):
                with self.assertRaises(api.WorkspaceRefused):
                    self.create(slug=bad)
        self.assertEqual(set(os.listdir(clients.clients_dir())) - before,
                         set())

    def test_case_and_padding_are_normalised_rather_than_refused(self):
        """"Acme Security" typed with a capital is somebody being human.
        The slug it becomes is still validated - normalising is not a way
        past the grammar."""
        try:
            entry = self.create(slug="  ACME-Security  ")
            self.assertEqual(entry["slug"], "acme-security")
        finally:
            self.cleanup("acme-security")

    def test_it_does_not_disturb_another_workspace(self):
        productive = ws.workspace("productive")
        try:
            self.create()
            self.assertEqual(ws.workspace("productive"), productive)
            self.assertTrue(clients.exists("productive"))
        finally:
            self.cleanup("acme-security")

    def test_the_new_workspace_reports_what_is_still_missing(self):
        """Created is not configured. The readiness list is the whole
        point of a starter that carries no ICP."""
        from src import repo as repo_module
        from src.web import api
        try:
            self.create()
            repo = repo_module.Repo.for_user("root@resonate.test",
                                             "acme-security")
            steps = api.onboarding(repo)["steps"]
            outstanding = {s["key"] for s in steps if not s["done"]}
            self.assertIn("icp", outstanding)
            self.assertIn("personas", outstanding)
            self.assertIn("batch", outstanding)
        finally:
            self.cleanup("acme-security")


class OnlyASuperAdminMayAdd(WebTest):

    def post(self, email, slug="acme-security"):
        session = self.signin(email)
        return session.post("/workspaces/create",
                            {"csrf": session.csrf(), "slug": slug,
                             "name": "Acme Security",
                             "domain": "acme-security.test"})

    def tearDown(self):
        for slug in ("acme-security",):
            rows = [r for r in ws.load() if r.get("slug") != slug]
            ws.save(rows)
            if clients.exists(slug):
                os.remove(clients.path_for(slug))
        super().tearDown()

    def test_a_workspace_admin_cannot(self):
        """Running your own client is not the same as adding somebody
        else's."""
        status, _, _ = self.post("admin@productive.test")
        self.assertIn(status, (403, 404))
        self.assertFalse(clients.exists("acme-security"))

    def test_an_operator_cannot(self):
        status, _, _ = self.post("ops@productive.test")
        self.assertIn(status, (403, 404))
        self.assertFalse(clients.exists("acme-security"))

    def test_a_viewer_cannot(self):
        status, _, _ = self.post("client@productive.test")
        self.assertIn(status, (403, 404))
        self.assertFalse(clients.exists("acme-security"))

    def test_a_super_admin_can(self):
        status, _, _ = self.post("root@resonate.test")
        self.assertIn(status, (200, 302, 303))
        self.assertTrue(clients.exists("acme-security"))
        self.assertIsNotNone(ws.workspace("acme-security"))

    def test_the_form_is_offered_only_to_a_super_admin(self):
        admin = self.signin("admin@productive.test")
        self.assertNotIn("/workspaces/create", admin.get("/workspaces")[1])
        root = self.signin("root@resonate.test")
        self.assertIn("/workspaces/create", root.get("/workspaces")[1])


if __name__ == "__main__":
    unittest.main()
