"""A workspace's settings have one answer, not two.

`/settings` lets a workspace admin change a short list of things - the
minimum company size, how many verifiers must agree, the daily volume - and
those are stored beside the workspace rather than written back into a YAML
file with comments in it. That part was right.

What was wrong is where they were applied. Only `repo.config` merged them,
and sixty-odd call sites plus every `--client` command line read
`clients.load` directly. So a workspace that had raised
`verification.required_confirmations` to three was verifying at two from
every command line, the web layer and the CLI disagreed about the same
client, and nothing anywhere said so.

The fix is one read path: `clients.load` applies them itself. These tests
assert that at the boundary a real operator would hit - a subprocess with
`--client` on the command line - rather than only through the helper,
because the helper was never the thing that was wrong.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from src import clients, repo as repo_module, verification, workspaces as ws

ENV = ("QUEUE", "CAMPAIGNS", "WORKSPACES", "AUDIT", "CLIENTS_DIR")


class Estate(unittest.TestCase):
    """One workspace, one client file, nothing shared with the repository."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-settings-")
        self._env = {k: os.environ.get(k) for k in ENV}
        work = os.path.join(self.tmp, "work")
        os.makedirs(work, exist_ok=True)
        os.environ["QUEUE"] = os.path.join(work, "queue.jsonl")
        os.environ["CAMPAIGNS"] = os.path.join(work, "campaigns.jsonl")
        os.environ["WORKSPACES"] = os.path.join(work, "workspaces.jsonl")
        os.environ["AUDIT"] = os.path.join(work, "audit.jsonl")
        os.environ["CLIENTS_DIR"] = os.path.join(self.tmp, "clients")

        clients.create("acme", "Acme", "acme.test")
        with open(clients.path_for("acme"), "a", encoding="utf-8",
                  newline="\n") as handle:
            handle.write("market:\n  size_min_employees: 10\n")
        ws.ensure("acme", "Acme", client="acme")
        ws.add_user("root@resonate.test", "Root", super_admin=True)

    def tearDown(self):
        for key, value in self._env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        shutil.rmtree(self.tmp, ignore_errors=True)

    def override(self, **values):
        ws.set_policy("acme", values, actor="test")

    def size(self, config):
        return (config.get("market") or {}).get("size_min_employees")


class OneAnswer(Estate):

    def test_the_file_is_the_baseline(self):
        self.assertEqual(self.size(clients.load("acme")), 10)

    def test_an_override_is_what_is_in_force(self):
        self.override(**{"market.size_min_employees": "250"})
        self.assertEqual(self.size(clients.load("acme")), 250)

    def test_the_web_layer_and_a_bare_load_agree(self):
        """The whole point. If these differ, one of them is wrong and
        nobody can tell which."""
        self.override(**{"market.size_min_employees": "250"})
        repo = repo_module.Repo.for_user("root@resonate.test", "acme")
        self.assertEqual(self.size(repo.config()),
                         self.size(clients.load("acme")))

    def test_a_verification_override_reaches_the_policy(self):
        """The one in this list where being out of step is a safety
        failure: a workspace that asked for three verifiers must not be
        verified at two by a command line that read the file."""
        self.override(**{"verification.required_confirmations": "3"})
        policy = verification.policy_for(clients.load("acme"))
        self.assertEqual(policy["required_confirmations"], 3)

    def test_the_floor_is_still_the_floor(self):
        """An override may tighten the rule. It may not loosen it."""
        with self.assertRaises(ws.NotOverridable):
            self.override(**{"verification.required_confirmations": "1"})

    def test_nothing_is_written_back_to_the_file(self):
        before = open(clients.path_for("acme"), encoding="utf-8").read()
        self.override(**{"market.size_min_employees": "250"})
        clients.load("acme")
        self.assertEqual(open(clients.path_for("acme"),
                              encoding="utf-8").read(), before)

    def test_a_client_no_workspace_claims_is_just_the_file(self):
        clients.create("orphan", "Orphan", "orphan.test")
        self.assertEqual(clients.load("orphan")["name"], "Orphan")

    def test_a_setting_that_is_no_longer_overridable_stops_applying(self):
        """It should stop applying, not stop the workspace loading."""
        rows = ws.load()
        for row in rows:
            if row.get("kind") == "workspace" and row.get("slug") == "acme":
                row["policy"] = {"market.retired_setting": "whatever"}
        ws.save(rows)
        self.assertNotIn("retired_setting", clients.load("acme").get("market")
                         or {})

    def test_naming_the_workspace_beats_inferring_it(self):
        self.override(**{"market.size_min_employees": "250"})
        self.assertEqual(self.size(clients.load("acme", workspace="acme")),
                         250)
        self.assertEqual(self.size(clients.load("acme", workspace="nobody")),
                         10)


class AnAmbiguousEstate(Estate):
    """Two workspaces claiming one client have no single answer.

    It cannot be built through the product any more - `ensure` refuses -
    so these build it the only way it can still arise, by writing the row
    the way a hand-edited table would.
    """

    def shadow(self):
        rows = ws.load()
        rows.append(ws.new_workspace("acme-two", "Acme Two", client="acme"))
        ws.save(rows)

    def test_the_product_will_not_create_one(self):
        """Records, campaigns and jobs are scoped by client; the audit log
        is scoped by workspace. Sharing a client shares every record while
        keeping the trails apart."""
        with self.assertRaises(ws.ClientTaken):
            ws.ensure("acme-two", "Acme Two", client="acme")

    def test_it_refuses_rather_than_picking_one(self):
        self.shadow()
        with self.assertRaises(clients.ConfigError) as caught:
            clients.load("acme")
        self.assertIn("acme-two", str(caught.exception))
        self.assertIn("acme", str(caught.exception))

    def test_a_caller_that_knows_which_one_is_unaffected(self):
        self.shadow()
        self.override(**{"market.size_min_employees": "250"})
        self.assertEqual(self.size(clients.load("acme", workspace="acme")),
                         250)


class OnTheCommandLine(Estate):
    """The boundary an operator actually hits.

    Asserted through a subprocess because that is what was broken: the
    helper was always capable of merging, and the thing that read the file
    without merging was `python -m src.<anything> --client acme`.
    """

    def seed(self):
        """One company of twelve people: over the file's minimum of ten,
        under an override of two hundred and fifty."""
        from src import store

        rec = store.new_record("acme-co", "cold", "acme", "Acme Co",
                               "acme-co.test")
        rec["company_facts"] = {"employees": 12,
                                "industry": "Professional services"}
        rec["contacts"] = [{"key": "acme-co-champ", "name": "Champ Person",
                            "email": "champ@acme-co.test",
                            "title": "Operations Manager"}]
        store.save([rec])

    def flags(self):
        """What a subprocess wrote into canonical state, read back."""
        from src import store

        env = dict(os.environ)
        env["PYTHONPATH"] = os.getcwd()
        proc = subprocess.run(
            [sys.executable, "-m", "src.personas", "--apply",
             "--id", "acme-co"],
            cwd=os.getcwd(), env=env, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        rec = store.get("acme-co")
        return (rec.get("company_facts") or {}).get("icp_flags") or []

    def test_the_command_line_reads_the_file(self):
        """Twelve people clears a minimum of ten, so nothing is flagged."""
        self.seed()
        self.assertEqual(
            [f for f in self.flags() if "minimum" in f], [])

    def test_the_command_line_reads_the_override_too(self):
        """The same company, the same file, one setting changed on a
        screen - and a different verdict written by a subprocess that
        never went near the web layer."""
        self.seed()
        self.override(**{"market.size_min_employees": "250"})
        flagged = [f for f in self.flags() if "minimum" in f]
        self.assertEqual(len(flagged), 1)
        self.assertIn("250", flagged[0])


if __name__ == "__main__":
    unittest.main()
