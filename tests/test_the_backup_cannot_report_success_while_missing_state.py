"""The TASK-265 review findings, as tests.

TASK-265 shipped a backup and a restore drill whose own tests were green.
Four defects survived them, and every one has the same shape: the thing
reports success while not doing the work.

1. `collect_state_files` built an expected set from `store.STATE_OVERRIDES`
   and then never used it - it returned `os.listdir(work_dir)`. A state file
   living anywhere else was omitted from the archive in silence. Its
   companion `_default_basename` table of 30 names was dead code AND already
   two entries behind `SUPERVISOR_LOCKS` / `SUPERVISOR_STATE`, which landed
   the same evening with TASK-263.
2. The lock was held across the directory listing and released before the
   zip, so the archive itself raced a checkpoint.
3. `prune_old_archives` deleted every archive past the retention age
   including the newest, so the run that noticed a month of missed backups
   would begin by deleting the only copy that existed.
4. The drill returned `ok: true` for a restore of zero records against a
   live store of zero records with no manifest - the vacuous pass that
   `docs/STORE-SQLITE-DESIGN-2026-09-22.md` §11 is written to refuse, and
   that this repository has now shipped three times.

And one more, from the task queued directly after it: `run_drill` called
`store.use_directory(tmp)` and never put the environment back, leaking a
QUEUE pointing at a deleted temp directory into every module that ran after
it. That is TASK-264's class exactly, shipped by TASK-265.
"""
import io
import os
import shutil
import tempfile
import time
import unittest
import zipfile

from src import store


class _BackupEnvTest(unittest.TestCase):
    """Isolated env: temp dir, saved/restored env vars, no live state."""

    def setUp(self):
        self._saved_env = dict(os.environ)
        self.tmp = tempfile.mkdtemp(prefix="rga-backup-review-")
        self.work_dir = os.path.join(self.tmp, "work")
        os.makedirs(self.work_dir, exist_ok=True)
        self.backup_dir = os.path.join(self.tmp, "backups")
        os.makedirs(self.backup_dir, exist_ok=True)
        os.environ["QUEUE"] = os.path.join(self.work_dir, "queue.jsonl")
        for var in store.STATE_OVERRIDES:
            os.environ.pop(var, None)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._saved_env)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _seed_queue(self, n=5):
        recs = []
        for i in range(n):
            state = "queued" if i % 2 else "verified"
            recs.append({
                "id": "review-%03d" % i,
                "state": state,
                "lane": "cold",
                "client": "productive",
                "company": "Acme %d" % i,
                "domain": "acme%d.test" % i,
                "drop_reason": "",
                "log": [{"step": state, "at": "2026-09-23T00:00:00+00:00",
                         "note": "seeded"}],
                "contacts": [{"key": "review-%03d:contact" % i,
                              "email": "review%d@acme%d.test" % (i, i),
                              "role": "decision-maker"}],
                "excluded": [],
            })
        store.append(recs)
        return store.stats()


class TestTheBackupCannotSilentlyOmitState(_BackupEnvTest):

    def test_an_override_outside_the_work_dir_is_archived_and_named(self):
        from scripts.backup_state import collect_state_files, create_archive
        self._seed_queue()

        elsewhere = os.path.join(self.tmp, "elsewhere")
        os.makedirs(elsewhere, exist_ok=True)
        stray = os.path.join(elsewhere, "spend-ledger.jsonl")
        with open(stray, "w") as f:
            f.write('{"spent": 1}\n')
        os.environ["SPEND_LEDGER"] = stray

        files, findings = collect_state_files(self.work_dir)

        self.assertIn(os.path.abspath(stray),
                      [os.path.abspath(p) for p in files],
                      "a ledger outside work/ was omitted from the archive")
        self.assertTrue(
            any("SPEND_LEDGER" in f for f in findings),
            "the omission was not named in the findings: %r" % (findings,))

        archive = create_archive(files, self.work_dir, self.backup_dir)
        with zipfile.ZipFile(archive) as zf:
            self.assertTrue(
                any(n.endswith("spend-ledger.jsonl") for n in zf.namelist()))

    def test_a_missing_override_file_is_a_finding_not_a_silence(self):
        from scripts.backup_state import collect_state_files
        self._seed_queue()
        os.environ["ACTION_LEDGER"] = os.path.join(
            self.tmp, "gone", "action-ledger.jsonl")

        _files, findings = collect_state_files(self.work_dir)
        self.assertTrue(any("ACTION_LEDGER" in f for f in findings),
                        "a missing ledger was not reported: %r" % (findings,))

    def test_a_missing_queue_is_a_finding(self):
        from scripts.backup_state import collect_state_files
        _files, findings = collect_state_files(self.work_dir)
        self.assertTrue(any("queue is not in the archive" in f
                            for f in findings), findings)

    def test_findings_make_the_exit_code_nonzero(self):
        from scripts.backup_state import main
        # No queue seeded, so the archive cannot be complete. A nightly cron
        # reading the exit code must not be told this worked.
        rc = main(["--backup-dir", self.backup_dir,
                   "--work-dir", self.work_dir])
        self.assertEqual(rc, 1)

    def test_a_complete_archive_exits_zero(self):
        """The refusal above must not be refusing everything."""
        from scripts.backup_state import main
        self._seed_queue()
        rc = main(["--backup-dir", self.backup_dir,
                   "--work-dir", self.work_dir])
        self.assertEqual(rc, 0)

    def test_no_hand_written_table_of_state_filenames_survives(self):
        """`store` owns the layout; a second copy is a second thing to be wrong."""
        import scripts.backup_state as mod
        src = io.open(mod.__file__, encoding="utf-8").read()
        self.assertNotIn("_default_basename", src)
        for name in ("campaigns.jsonl", "spend-ledger.jsonl",
                     "action-ledger.jsonl", "client-approval.jsonl"):
            self.assertNotIn(
                '"' + name + '"', src,
                name + " is spelled out in backup_state.py; ask store instead")


class TestTheArchiveIsTakenUnderTheLock(_BackupEnvTest):

    def test_the_zip_happens_inside_the_lock_window(self):
        """A lock held across the listing and dropped before the zip is not
        a lock. Proven by observing that the lock file exists while
        `create_archive` runs, rather than by reading the source."""
        import scripts.backup_state as mod
        self._seed_queue()

        observed = {}
        real_create = mod.create_archive

        def watching_create(file_list, work_dir, backup_dir):
            observed["locked"] = os.path.exists(store.lock_path())
            return real_create(file_list, work_dir, backup_dir)

        mod.create_archive = watching_create
        try:
            mod.main(["--backup-dir", self.backup_dir,
                      "--work-dir", self.work_dir])
        finally:
            mod.create_archive = real_create

        self.assertTrue(observed.get("locked"),
                        "the archive was written with the queue unlocked")


class TestThePruneKeepsTheOnlyCopy(_BackupEnvTest):

    def test_the_newest_archive_survives_however_old_it_is(self):
        from scripts.backup_state import prune_old_archives
        old = time.time() - 400 * 86400
        for i in range(3):
            fp = os.path.join(self.backup_dir, "ancient-%d.zip" % i)
            with zipfile.ZipFile(fp, "w") as zf:
                zf.writestr("x", "y")
            os.utime(fp, (old + i, old + i))

        removed = prune_old_archives(self.backup_dir, retention_days=14)

        remaining = sorted(f for f in os.listdir(self.backup_dir)
                           if f.endswith(".zip"))
        self.assertEqual(remaining, ["ancient-2.zip"],
                         "the prune deleted the last copy that existed")
        self.assertEqual(len(removed), 2)


class TestTheDrillRefusesAVacuousPass(_BackupEnvTest):

    def test_an_empty_restore_is_not_ok(self):
        from scripts.backup_state import collect_state_files, create_archive
        from scripts.restore_drill import run_drill
        # Live store and archive both hold zero records. `stats_match` is
        # perfectly true and means nothing at all.
        open(os.path.join(self.work_dir, "queue.jsonl"), "w").close()
        files, _ = collect_state_files(self.work_dir)
        archive = create_archive(files, self.work_dir, self.backup_dir)

        result = run_drill(archive, manifest_data={"records": 0},
                           live_stats={"records": 0, "states": {},
                                       "lanes": {}},
                           live_dir=self.work_dir)

        self.assertFalse(result["ok"],
                         "the drill reported ok having restored nothing")
        self.assertIn("0 records", result["error"] or "")

    def test_no_manifest_is_not_a_pass(self):
        from scripts.backup_state import collect_state_files, create_archive
        from scripts.restore_drill import run_drill
        live = self._seed_queue(5)
        files, _ = collect_state_files(self.work_dir)
        archive = create_archive(files, self.work_dir, self.backup_dir)

        result = run_drill(archive, manifest_data={}, live_stats=live,
                           live_dir=self.work_dir)

        self.assertFalse(
            result["ok"],
            "the drill passed with nothing independent to check against")

    def test_a_real_restore_with_a_manifest_is_ok(self):
        """The two refusals above must not be refusing everything."""
        from scripts.backup_state import collect_state_files, create_archive
        from scripts.restore_drill import run_drill
        live = self._seed_queue(5)
        files, _ = collect_state_files(self.work_dir)
        archive = create_archive(files, self.work_dir, self.backup_dir)

        result = run_drill(archive,
                           manifest_data={"records": live["records"]},
                           live_stats=live, live_dir=self.work_dir)

        self.assertTrue(result["ok"], result.get("error"))
        self.assertEqual(result["restored_records"], 5)


class TestTheDrillDoesNotLeakItsTempDirIntoTheEnvironment(_BackupEnvTest):
    """TASK-264's class, shipped by TASK-265 and caught at review."""

    def test_queue_and_overrides_are_what_they_were(self):
        from scripts.backup_state import collect_state_files, create_archive
        from scripts.restore_drill import run_drill
        live = self._seed_queue(5)
        files, _ = collect_state_files(self.work_dir)
        archive = create_archive(files, self.work_dir, self.backup_dir)

        os.environ["SPEND_LEDGER"] = os.path.join(self.work_dir,
                                                  "poison.jsonl")
        before_queue = os.environ["QUEUE"]
        before_ledger = os.environ["SPEND_LEDGER"]

        run_drill(archive, manifest_data={"records": live["records"]},
                  live_stats=live, live_dir=self.work_dir)

        self.assertEqual(
            os.environ.get("QUEUE"), before_queue,
            "the drill left QUEUE pointing at its deleted temp dir")
        self.assertEqual(
            os.environ.get("SPEND_LEDGER"), before_ledger,
            "the drill cleared a STATE_OVERRIDES entry and did not put "
            "it back")


if __name__ == "__main__":
    unittest.main()
