"""Onboard a client from nothing, without editing a line of Python.

The claim this file exists to test is that Productive is a reference
implementation rather than the only shape of client the product understands.
So: create a workspace, configure it, import domains, qualify them, and reach
a campaign - through the same interfaces an operator has, in a throwaway
estate, with no provider calls and no source changes.

Where the platform cannot do something without a code change, the test says so
by name rather than working around it. A workaround here would be the test
proving the opposite of what it claims.
"""
import io
import json
import os
import shutil
import tempfile
import unittest

from src import clients, ingest, qualify, store
from src.web import upload

SLUG = "acceptance-co"


class ANewClientFromZero(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-newclient-")
        os.makedirs(os.path.join(self.tmp, "work"), exist_ok=True)
        self.saved = {name: os.environ.get(name)
                      for name in ("QUEUE", "OUT", "CLIENTS_DIR", "MX_CACHE")}
        os.environ["QUEUE"] = os.path.join(self.tmp, "work", "queue.jsonl")
        os.environ["OUT"] = os.path.join(self.tmp, "out")
        os.environ["MX_CACHE"] = os.path.join(self.tmp, "mx-cache.json")
        # A throwaway client directory, seeded with the shipped example so the
        # test cannot write into the real one.
        self.clients_dir = os.path.join(self.tmp, "clients")
        os.makedirs(self.clients_dir, exist_ok=True)
        os.environ["CLIENTS_DIR"] = self.clients_dir
        self.addCleanup(self.restore)

    def restore(self):
        for name, value in self.saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        shutil.rmtree(self.tmp, ignore_errors=True)

    def create(self):
        return clients.create(SLUG, "Acceptance Co", "acceptance.test",
                              booking_link="https://acceptance.test/book",
                              created_by="acceptance-test")

    # ------------------------------------------------------- 1. the client

    def test_a_client_can_be_created_without_touching_the_filesystem_by_hand(self):
        path = self.create()
        self.assertTrue(os.path.exists(path))
        self.assertIn(SLUG, path)

    def test_creating_the_same_client_twice_is_refused(self):
        self.create()
        with self.assertRaises(clients.ConfigError):
            self.create()

    def test_a_hostile_slug_never_reaches_a_path(self):
        for bad in ("../escape", "Acme", "a b", "con", ""):
            with self.assertRaises(clients.ConfigError):
                clients.create(bad, "X", "x.test")

    def test_the_new_client_loads(self):
        self.create()
        config = clients.load(SLUG)
        self.assertEqual(config["name"], "Acceptance Co")
        self.assertEqual(config["domain"], "acceptance.test")

    # ------------------------------------------- 2. it is nobody else's client

    def test_the_starter_names_no_other_client(self):
        """The template used to say `cadence: productive_default`."""
        with io.open(self.create(), encoding="utf-8") as handle:
            body = handle.read().lower()
        for name in ("productive", "ironvault", "contactout"):
            self.assertNotIn(name, body, f"the starter mentions {name}")

    def test_its_segment_keys_carry_its_own_name(self):
        """This is what a real client's name in a global default looked like."""
        from src import campaignseg
        self.create()
        prefix = campaignseg.settings(clients.load(SLUG))["client_prefix"]
        self.assertEqual(prefix, "ACCEPTANCECO")
        self.assertNotIn("PRODUCTIVE", prefix)

    # ------------------------------------------------------- 3. configuration

    def test_markets_set_by_an_operator_reach_the_scorer(self):
        """`/settings` writes `market.geos`; the scorer reads `icp.markets`.

        They were two names for one answer and only one was read.
        """
        from src import icp
        self.create()
        config = dict(clients.load(SLUG),
                      market={"geos": ["United Kingdom", "Nordics"]})
        self.assertEqual(icp.settings(config)["markets"],
                         ["United Kingdom", "Nordics"])

    def test_an_unconfigured_client_qualifies_nobody_rather_than_everybody(self):
        """Absence of an ICP must not read as 'everything fits'."""
        from src import icp
        self.create()
        rec = store.new_record("r1", "domains", SLUG, "X", "x.test")
        verdict = icp.score(rec, clients.load(SLUG))
        self.assertNotEqual(verdict["icp_status"], icp.QUALIFIED)

    # --------------------------------------------------------- 4. import

    def test_domains_import_through_the_operator_path(self):
        self.create()
        blob = b"domain\r\nalpha.test\r\nbravo.test\r\nALPHA.test\r\nnot a domain\r\n"
        report = upload.parse(blob, client=SLUG)
        self.assertEqual(report["unique"], 2)
        self.assertEqual(report["duplicates"], 1)
        self.assertEqual(report["invalid"], 1)
        self.assertTrue(all(e.get("reason") for e in report["excluded"]))

    def test_the_cli_import_agrees_with_the_browser(self):
        self.create()
        path = os.path.join(self.tmp, "in.csv")
        io.open(path, "w", encoding="utf-8", newline="\n").write(
            "company,domain\nAlpha,alpha.test\nJunk,not a domain\n")
        result = ingest.run(path, SLUG, "domains", suppress_path=None)
        self.assertEqual(len(result["queued"]), 1)
        self.assertEqual(len(result["dropped"]), 1)

    # ------------------------------------------------------ 5. it is isolated

    def test_the_new_client_cannot_see_another_clients_records(self):
        from src import repo
        self.create()
        with store.transaction() as rows:
            rows.append(store.new_record("mine", "domains", SLUG, "A", "a.test"))
            rows.append(store.new_record("theirs", "domains", "productive",
                                         "B", "b.test"))
        mine = repo.Repo.for_client(SLUG).records()
        self.assertEqual([r["id"] for r in mine], ["mine"])

    # ------------------------------------------------- 6. what still needs code

    def test_a_client_can_declare_the_market_it_sells_to(self):
        """Was a recorded limit; now a supported one.

        The taxonomy was fourteen categories of agency and professional
        services - Productive's market - and `extra_keywords` only let a
        client add words to one of *those*. A client selling to clinics had no
        expressible vertical, so every company scored UNKNOWN and the ICP
        model sat idle. `segmentation.verticals` closes it in config.
        """
        from src import segments
        self.create()
        config = dict(clients.load(SLUG), segmentation={"verticals": {
            "Dental Clinic": {"keywords": ["dental practice", "orthodontist"],
                              "kind": "service"}}})
        rec = store.new_record("r2", "domains", SLUG, "Smiles", "smiles.test")
        rec["company_facts"] = {"industry": "dental practice",
                                "specialties": ["orthodontist"]}
        self.assertEqual(segments.classify(rec, config)["vertical"],
                         "Dental Clinic")

    def test_and_still_cannot_rename_one_of_the_built_ins(self):
        """A rename orphans every campaign segment using the old name."""
        from src import segments
        self.create()
        hijack = dict(clients.load(SLUG), segmentation={"verticals": {
            segments.SEO: {"keywords": ["x"], "kind": "non_icp"}}})
        self.assertEqual(segments.settings(hijack)["verticals"], {})


if __name__ == "__main__":
    unittest.main()
