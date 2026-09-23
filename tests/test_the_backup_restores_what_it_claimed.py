"""A backup nobody has restored is a belief, not a backup.

TASK-265: the restore drill is the deliverable. These tests prove:

1. The archive contains every file STATE_OVERRIDES names, plus the queue
   and the SQLite store.
2. config/.env is NOT in the archive.
3. The drill restores into a temp dir and the live directory is untouched.
4. A corrupted archive FAILS loudly.
5. Retention prunes at the configured age and keeps the newest.
6. Neither script writes to the live work/ directory.
"""
import io
import json
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
        self.tmp = tempfile.mkdtemp(prefix="rga-backup-test-")
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
                "id": f"test-{i:03d}",
                "state": state,
                "lane": "cold",
                "client": "productive",
                "company": f"Acme {i}",
                "domain": f"acme{i}.test",
                "drop_reason": "",
                "log": [{"step": state, "at": "2026-09-22T00:00:00+00:00",
                         "note": "seeded"}],
                "contacts": [{"key": f"test-{i:03d}:contact",
                              "email": f"test{i}@acme{i}.test",
                              "role": "decision-maker"}],
                "excluded": [],
            })
        store.append(recs)
        return store.stats()

    def _seed_state_files(self):
        names = [
            "campaigns.jsonl", "jobs.jsonl", "workspaces.jsonl",
            "audit.jsonl", "senders.jsonl", "notifications.jsonl",
            "reports.jsonl", "report-drafts.jsonl",
            "mx-cache.json", "observability.jsonl", "checkpoints.json",
            "replywatch.json", "tag-outbox.jsonl", "agency-dnc.jsonl",
            "signals.jsonl", "gtm.jsonl", "discovery.jsonl",
            "clientreview.jsonl", "crawl-cache.json",
            "knowledge-pack.json", "slack-threads.jsonl",
            "slack-requests.jsonl", "slack-followups.jsonl",
            "action-ledger.jsonl", "spend-ledger.jsonl",
            "lead-observations.jsonl", "watch-events", "heartbeat",
            "client-approval.jsonl", "candidates.jsonl",
        ]
        for name in names:
            with open(os.path.join(self.work_dir, name), "w") as f:
                f.write("{}\n")
        db_path = os.path.join(self.work_dir, "queue.db")
        with open(db_path, "w") as f:
            f.write("SQLITE-FORMAT")
        return names


class TestBackupContainsEveryStateOverride(_BackupEnvTest):

    def test_archive_carries_every_override_file(self):
        from scripts.backup_state import collect_state_files, create_archive
        self._seed_queue()
        seeded = self._seed_state_files()

        files, _findings = collect_state_files()
        basenames = {os.path.basename(p) for p in files}
        for name in seeded:
            self.assertIn(name, basenames, f"{name} not collected")
        self.assertIn("queue.jsonl", basenames)
        self.assertIn("queue.db", basenames)

        archive = create_archive(files, self.work_dir, self.backup_dir)
        with zipfile.ZipFile(archive) as zf:
            archived = set(zf.namelist())
        for name in seeded:
            self.assertIn(name, archived)
        self.assertIn("queue.jsonl", archived)

    def test_config_env_is_absent_from_archive(self):
        from scripts.backup_state import collect_state_files, create_archive
        self._seed_queue()
        self._seed_state_files()

        fake_env = os.path.join(self.tmp, ".env")
        with open(fake_env, "w") as f:
            f.write("SECRET=value\n")

        files, _findings = collect_state_files()
        archive = create_archive(files, self.work_dir, self.backup_dir)
        with zipfile.ZipFile(archive) as zf:
            for name in zf.namelist():
                self.assertFalse(
                    name.endswith(".env") or name.endswith("/.env"),
                    f"config/.env leaked into archive as {name}",
                )


class TestDrillSucceeds(_BackupEnvTest):

    def test_restored_stats_match_source(self):
        from scripts.backup_state import collect_state_files, create_archive
        from scripts.restore_drill import run_drill

        live_stats = self._seed_queue()
        self._seed_state_files()

        files, _findings = collect_state_files()
        archive = create_archive(files, self.work_dir, self.backup_dir)

        manifest = {
            "records": live_stats["records"],
            "stages": dict(live_stats["states"]),
        }

        result = run_drill(
            archive,
            manifest_data=manifest,
            live_stats=live_stats,
        )
        self.assertTrue(result["ok"], result.get("error", ""))
        self.assertEqual(result["restored_stats"]["records"],
                         live_stats["records"])
        self.assertFalse(result["temp_dir_exists"])


class TestCorruptedArchiveFails(_BackupEnvTest):

    def test_truncated_archive_refuses_to_restore(self):
        from scripts.backup_state import collect_state_files, create_archive
        from scripts.restore_drill import run_drill

        self._seed_queue()
        self._seed_state_files()

        files, _findings = collect_state_files()
        archive = create_archive(files, self.work_dir, self.backup_dir)

        with open(archive, "rb") as f:
            data = f.read()
        with open(archive, "wb") as f:
            f.write(data[:len(data) // 4])

        result = run_drill(archive, manifest_data={},
                           live_stats={"records": 5})
        self.assertFalse(result["ok"])
        self.assertIn("error", result)


class TestRetention(_BackupEnvTest):

    def test_prune_keeps_newest_and_removes_oldest(self):
        from scripts.backup_state import prune_old_archives

        ages_days = [20, 16, 10, 5, 1]
        archives = []
        for i, age in enumerate(ages_days):
            path = os.path.join(self.backup_dir, f"backup-{i}.zip")
            with zipfile.ZipFile(path, "w") as zf:
                zf.writestr("queue.jsonl", "")
            mtime = time.time() - age * 86400
            os.utime(path, (mtime, mtime))
            archives.append(path)

        removed = prune_old_archives(self.backup_dir, retention_days=14)
        self.assertEqual(len(removed), 2)

        remaining = sorted(os.listdir(self.backup_dir))
        self.assertEqual(len(remaining), 3)
        self.assertIn("backup-2.zip", remaining)
        self.assertIn("backup-3.zip", remaining)
        self.assertIn("backup-4.zip", remaining)


class TestLiveDirectoryUntouched(_BackupEnvTest):

    def test_drill_does_not_modify_live_mtimes(self):
        from scripts.backup_state import collect_state_files, create_archive
        from scripts.restore_drill import run_drill

        self._seed_queue()
        self._seed_state_files()

        files, _findings = collect_state_files()
        archive = create_archive(files, self.work_dir, self.backup_dir)

        mtimes_before = {}
        for fn in os.listdir(self.work_dir):
            fp = os.path.join(self.work_dir, fn)
            if os.path.isfile(fp):
                mtimes_before[fn] = os.path.getmtime(fp)

        time.sleep(0.1)

        live_stats = store.stats()
        manifest = {"records": live_stats["records"],
                     "stages": dict(live_stats["states"])}
        run_drill(archive, manifest_data=manifest, live_stats=live_stats)

        for fn, mtime_before in mtimes_before.items():
            fp = os.path.join(self.work_dir, fn)
            if os.path.isfile(fp):
                self.assertAlmostEqual(
                    os.path.getmtime(fp), mtime_before, places=2,
                    msg=f"{fn} mtime changed during drill",
                )


class TestNeitherScriptWritesLive(_BackupEnvTest):

    def test_backup_does_not_write_to_work_during_archive(self):
        from scripts.backup_state import collect_state_files, create_archive

        self._seed_queue()
        self._seed_state_files()

        snapshot = set(os.listdir(self.work_dir))
        files, _findings = collect_state_files()
        create_archive(files, self.work_dir, self.backup_dir)
        after = set(os.listdir(self.work_dir))
        self.assertEqual(snapshot, after)


class TestDrillComparesManifest(_BackupEnvTest):

    def test_manifest_mismatch_is_reported(self):
        from scripts.backup_state import collect_state_files, create_archive
        from scripts.restore_drill import run_drill

        live_stats = self._seed_queue()
        self._seed_state_files()

        files, _findings = collect_state_files()
        archive = create_archive(files, self.work_dir, self.backup_dir)

        wrong_manifest = {
            "records": live_stats["records"] + 999,
            "stages": dict(live_stats["states"]),
        }
        result = run_drill(archive, manifest_data=wrong_manifest,
                           live_stats=live_stats)
        self.assertFalse(result["manifest_matches"])
        self.assertFalse(result["ok"])


if __name__ == "__main__":
    unittest.main()
