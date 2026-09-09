"""State on a mounted volume: one lever, everything follows, nothing left behind.

A container filesystem is ephemeral. The whole of production persistence
for this build is therefore one question - **when `QUEUE` points at a
mounted volume, does every state file actually go there?** - and the
failure mode if the answer is no is the worst kind: an empty store is a
*valid* store. Nothing downstream can tell a fresh workspace from one
whose records were deleted on the last deploy. There is no exception, no
error and no missing file to notice.

`tests/test_invariants.py` already guards the *set*: it walks `src/` for
state lookups and fails if one is missing from `store.STATE_OVERRIDES`.
What it does not do is put a record through and look at where the bytes
landed. These do.

Deliberately asserted on the filesystem rather than on the module: the
question is not whether `store` computes the right path, it is whether the
process wrote to the volume.
"""
import io
import os
import shutil
import tempfile
import unittest

from src import config, store, workspaces
from src.web import app, demodata

# What a Railway volume mount looks like. The path is not special - what
# matters is that it is somewhere the repository is not.
MOUNT = "data"


class Mounted(unittest.TestCase):

    ENV = ("QUEUE", "APP_MODE", "MX_CACHE", "OUT", "CLIENTS_DIR",
           "AUTH_PROVIDER", "AUTH_ISSUER", "AUTH_CLIENT_ID",
           "AUTH_CLIENT_SECRET", "AUTH_REDIRECT_URL") + store.STATE_OVERRIDES

    def setUp(self):
        self._prev = {k: os.environ.get(k) for k in self.ENV}
        self.root = tempfile.mkdtemp(prefix="rga-volume-")
        self.mount = os.path.join(self.root, MOUNT)
        # Exactly what a deployment does: one variable, pointed at the mount.
        store.use_directory(os.path.join(self.mount, "work"))
        os.environ["MX_CACHE"] = os.path.join(self.mount, "mx-cache.json")
        os.environ["OUT"] = os.path.join(self.mount, "out")
        os.environ["CLIENTS_DIR"] = os.path.join(self.mount, "clients")

    def tearDown(self):
        for key, value in self._prev.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        shutil.rmtree(self.root, ignore_errors=True)

    def written(self):
        """Every file that ended up on the mount."""
        found = []
        for dirpath, _dirnames, filenames in os.walk(self.mount):
            for name in filenames:
                found.append(os.path.join(dirpath, name))
        return found


class EverythingFollowsTheQueue(Mounted):

    def test_a_populated_estate_lands_entirely_on_the_mount(self):
        demodata.install()
        names = {os.path.basename(p) for p in self.written()}
        # Not an exhaustive list - an exhaustive list here would be a second
        # copy of store's layout. These are the files whose loss would be
        # unrecoverable: the records, the campaigns, and who may see them.
        for essential in ("queue.jsonl", "campaigns.jsonl",
                          "workspaces.jsonl"):
            self.assertIn(essential, names,
                          f"{essential} did not land on the volume")

    def test_nothing_was_written_beside_the_repository_instead(self):
        """The failure this exists for: one file that missed the redirect.

        `store.STATE_OVERRIDES` is what makes the whole set move together,
        and a module added later that reads its own environment variable
        without joining that tuple keeps pointing at the repository's own
        `work/`. Here that would be somebody else's machine; in production
        it is the ephemeral disk.
        """
        repo_work = os.path.abspath(
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "work"))

        def snapshot():
            if not os.path.isdir(repo_work):
                return {}
            # Size as well as name. An override left pointing at the real
            # directory usually *appends* to a file that is already there,
            # so comparing the listing alone would see nothing change.
            return {n: os.path.getsize(os.path.join(repo_work, n))
                    for n in os.listdir(repo_work)
                    if os.path.isfile(os.path.join(repo_work, n))}

        before = snapshot()

        demodata.install()
        workspaces.record("volume@test", None, "security.refused",
                          resource_type="request", resource_id="probe",
                          reason="a write that touches the audit log")

        self.assertEqual(snapshot(), before,
                         "a state write escaped the mount and landed in the "
                         "repository's own work/ directory")

    def test_no_state_override_points_off_the_mount(self):
        """The same question asked of the environment rather than the disk.

        `store.use_directory` clears every override in
        `store.STATE_OVERRIDES` so they fall back to the queue's directory.
        One left set - a module that reads its own variable and was never
        added to that tuple - keeps writing wherever it was pointed, which
        in a container is the disk that disappears.
        """
        # Set every one of them somewhere wrong *first*. That is the real
        # shape: a leftover variable in a deployment's environment, or a
        # test harness that pointed one somewhere and moved on. Asserting
        # against an environment that was already empty proves nothing,
        # which an attack on `use_directory` demonstrated by surviving.
        stale = os.path.join(self.root, "not-the-volume")
        for name in store.STATE_OVERRIDES:
            os.environ[name] = os.path.join(stale, name.lower() + ".jsonl")

        store.use_directory(os.path.join(self.mount, "work"))
        mount = os.path.abspath(self.mount)
        for name in ("QUEUE",) + store.STATE_OVERRIDES:
            value = os.environ.get(name)
            if not value:
                continue
            self.assertTrue(os.path.abspath(value).startswith(mount),
                            f"{name} points outside the volume")

    def test_the_queue_resolves_under_the_mount(self):
        self.assertTrue(
            os.path.abspath(store.queue_path()).startswith(
                os.path.abspath(self.mount)))
        self.assertTrue(
            os.path.abspath(store.campaigns_path()).startswith(
                os.path.abspath(self.mount)))


class ItSurvivesTheProcess(Mounted):

    def test_state_written_now_is_readable_after_a_restart(self):
        """A deploy replaces the process, not the volume.

        Simulated the only way it can be in-process: write, drop every
        cached path and handle by re-pointing the store at the same
        directory, then read. What is being checked is that the bytes are
        on the mount rather than in memory.
        """
        _, records, _ = demodata.install()
        self.assertTrue(records)
        before = {r["id"] for r in store.load()}
        self.assertTrue(before)

        # The "restart": nothing in this process remembers anything.
        store.use_directory(os.path.join(self.mount, "work"))

        after = {r["id"] for r in store.load()}
        self.assertEqual(after, before)

    def test_an_empty_mount_reads_as_empty_rather_than_failing(self):
        """Which is exactly why the startup check matters.

        A fresh volume is indistinguishable from a wiped one, so nothing
        downstream can raise the alarm. The alarm has to be raised before
        the process starts, and `test_production_refuses_without_it` below
        is where.
        """
        self.assertEqual(store.load(), [])


class ProductionInsistsOnIt(Mounted):

    def configure_auth(self):
        os.environ.update({
            "AUTH_PROVIDER": "oidc",
            "AUTH_ISSUER": "https://issuer.test",
            "AUTH_CLIENT_ID": "client",
            "AUTH_CLIENT_SECRET": "secret",
            "AUTH_REDIRECT_URL": "https://app.test/auth/callback",
        })

    def test_production_refuses_without_it(self):
        """Authentication is fine here. Persistence is what stops it."""
        self.configure_auth()
        os.environ["APP_MODE"] = "production"
        os.environ.pop("QUEUE", None)
        with self.assertRaises(RuntimeError) as caught:
            app.serve(0, demo=True)
        self.assertIn("QUEUE", str(caught.exception))

    def test_production_starts_once_it_is_pointed_somewhere(self):
        """The other half. A check that cannot be satisfied is a wall."""
        self.configure_auth()
        os.environ["APP_MODE"] = "production"
        os.environ["QUEUE"] = os.path.join(self.mount, "work", "queue.jsonl")
        server = app.serve(0, demo=False, host="127.0.0.1")
        try:
            self.assertTrue(server.server_address[1])
        finally:
            server.server_close()

    def test_a_database_url_is_not_what_it_wants(self):
        """There is no SQL backend in this build.

        Setting one satisfies nothing, and provisioning Postgres for it
        would leave an empty database beside the real state on disk.
        """
        self.configure_auth()
        os.environ["APP_MODE"] = "production"
        os.environ.pop("QUEUE", None)
        os.environ["DATABASE_URL"] = "postgres://not-a-substitute"
        try:
            self.assertIn("QUEUE",
                          config.report(config.PRODUCTION)["blockers"])
        finally:
            os.environ.pop("DATABASE_URL", None)


if __name__ == "__main__":
    unittest.main()
