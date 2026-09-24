"""2e — the backup restores, and shipping it off-host refuses.

A BACKUP THAT HAS NEVER BEEN RESTORED IS NOT A BACKUP. It is a file with a
date in its name. The same sentence as the rollback in 2c, and for the same
reason: both are the thing you find out about on the worst day.

So the drill is run here for real — back up a fixture estate, restore it into
a throwaway directory, and compare BY NAME AND BY HASH. A drill comparing
counts would pass while a file came back truncated, which makes it exactly
the kind of green that cannot fail.

THE REFUSALS ARE THE OTHER HALF, and they are the operator's instruction for
2e: named, unfilled inputs that refuse rather than a guessed destination or
an unencrypted archive leaving the host. Three of them are asserted:

  - `--ship` refuses while BACKUP_TARGET / BACKUP_ENCRYPTION are unset, and
    names both.
  - a restore into a non-empty directory refuses, because a restore is the
    one operation that can destroy what it exists to protect.
  - `secrets.env` is never in an archive and never restored from one.

NO REAL STATE IS TOUCHED. Every test builds its own fixture estate in a temp
directory and passes `--state-dir`; nothing reads or writes the real `work/`.
"""
import io
import os
import subprocess
import sys
import tarfile
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

SCRIPT = os.path.join(ROOT, "scripts", "server", "backup.py")


def _run(*args, env=None):
    e = dict(os.environ)
    # The two operator values must be ABSENT for the refusal tests, and a
    # developer who has them set locally would otherwise see a different
    # answer than CI.
    e.pop("BACKUP_TARGET", None)
    e.pop("BACKUP_ENCRYPTION", None)
    e.update(env or {})
    return subprocess.run([sys.executable, SCRIPT] + list(args),
                          cwd=ROOT, env=e, capture_output=True, text=True)


class _Estate(unittest.TestCase):
    """A fixture `work/` with the shapes the real one has."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-backup-")
        self.state = os.path.join(self.tmp, "work")
        self.into = os.path.join(self.tmp, "backups")
        os.makedirs(os.path.join(self.state, "heartbeat"))
        os.makedirs(os.path.join(self.state, "watch-events"))
        self._write("queue.jsonl", '{"record_id": "r1", "stage": "queued"}\n')
        self._write("campaigns.jsonl",
                    '{"campaign_id": "c497", "bison_campaign_id": 497}\n')
        self._write("heartbeat/bison-497.json", '{"at": 1, "ok": true}\n')
        self._write("watch-events/heyreach-605732.jsonl", "WATCHING 605732\n")

    def _write(self, rel, text):
        path = os.path.join(self.state, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with io.open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        return path

    def _module(self):
        """The script imported as a module, so its functions can be tested
        directly rather than only through the command line."""
        import importlib.util
        spec = importlib.util.spec_from_file_location("bk", SCRIPT)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def _archives(self):
        return [os.path.join(self.into, n) for n in sorted(os.listdir(self.into))
                if n.endswith(".tar.gz")]


class TheDrillIsEvidenceAndNotIntention(_Estate):

    def test_the_drill_passes_on_a_healthy_estate(self):
        proc = _run("--drill", "--state-dir", self.state, "--into", self.into)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        self.assertIn("DRILL PASSED", proc.stdout)
        self.assertIn("every file came back, byte for byte", proc.stdout)

    def test_the_drill_compares_hashes_and_not_counts(self):
        """The assertion that stops this being a green that cannot fail: a
        file that comes back with the same name and different bytes must
        fail the drill."""
        bk = self._module()
        before = bk.inventory(self.state)
        self._write("queue.jsonl", '{"record_id": "r1", "stage": "DROPPED"}\n')
        after = bk.inventory(self.state)
        self.assertEqual(set(before), set(after), "the file names are the same")
        self.assertNotEqual(before["queue.jsonl"], after["queue.jsonl"],
                            "a count-based comparison would see no difference")

    def test_the_drills_own_comparison_fails_on_equal_counts(self):
        """The one a mutation caught. Replacing the whole comparison with
        `len(before) == len(after)` left every drill test green, because a
        healthy restore has equal counts either way - and the test meant to
        guard this asserted on `inventory()`, which the drill's comparison
        never goes through. So it is asserted HERE, on the function the
        drill actually calls, with same names and different bytes."""
        bk = self._module()
        before = {"queue.jsonl": "aaa", "campaigns.jsonl": "bbb"}
        after = {"queue.jsonl": "TRUNCATED", "campaigns.jsonl": "bbb"}
        self.assertEqual(len(before), len(after), "the counts are equal")
        ok, missing, extra, changed = bk.compare(before, after)
        self.assertFalse(ok, "a count-only comparison would have passed")
        self.assertEqual(["queue.jsonl"], changed)
        self.assertEqual([], missing)
        self.assertEqual([], extra)

    def test_the_drills_comparison_catches_a_file_that_never_came_back(self):
        bk = self._module()
        ok, missing, _extra, _changed = bk.compare(
            {"queue.jsonl": "aaa", "campaigns.jsonl": "bbb"},
            {"queue.jsonl": "aaa"})
        self.assertFalse(ok)
        self.assertEqual(["campaigns.jsonl"], missing)

    def test_backing_up_a_directory_that_does_not_exist_refuses(self):
        """An empty archive restores cleanly over a live estate."""
        proc = _run("--backup", "--state-dir",
                    os.path.join(self.tmp, "nope"), "--into", self.into)
        self.assertNotEqual(0, proc.returncode)
        self.assertIn("REFUSING", proc.stderr)


class ARestoreWillNotDestroyWhatItProtects(_Estate):

    def test_restoring_into_a_non_empty_directory_refuses(self):
        _run("--backup", "--state-dir", self.state, "--into", self.into)
        archive = self._archives()[0]
        proc = _run("--restore", archive, "--into", self.state)
        self.assertNotEqual(0, proc.returncode)
        self.assertIn("restore over live state", proc.stderr)

    def test_force_allows_it_because_the_decision_is_the_operators(self):
        _run("--backup", "--state-dir", self.state, "--into", self.into)
        archive = self._archives()[0]
        proc = _run("--restore", archive, "--into", self.state, "--force")
        self.assertEqual(0, proc.returncode, proc.stderr)

    def test_a_member_escaping_the_destination_is_refused(self):
        """The archives this script writes never contain one. The archives it
        READS are whatever was handed to it."""
        evil = os.path.join(self.tmp, "evil.tar.gz")
        payload = os.path.join(self.tmp, "payload")
        with io.open(payload, "w", encoding="utf-8") as fh:
            fh.write("x")
        with tarfile.open(evil, "w:gz") as tar:
            tar.add(payload, arcname="../escaped.txt")
        proc = _run("--restore", evil, "--into",
                    os.path.join(self.tmp, "fresh"))
        self.assertNotEqual(0, proc.returncode)
        self.assertIn("escapes the destination", proc.stderr)


class TheSecretsFileIsNeverInABackup(_Estate):

    def test_it_is_excluded_from_the_archive(self):
        self._write("secrets.env", "BISON_KEY=zz-not-a-real-key\n")
        _run("--backup", "--state-dir", self.state, "--into", self.into)
        with tarfile.open(self._archives()[0], "r:gz") as tar:
            names = tar.getnames()
        self.assertNotIn("secrets.env", names)
        self.assertIn("queue.jsonl", names)

    def test_an_archive_containing_one_is_refused_on_restore(self):
        """A backup is a copy that travels, and the whole design of that file
        is that it does not."""
        bad = os.path.join(self.tmp, "bad.tar.gz")
        secret = self._write("secrets.env", "BISON_KEY=zz-not-a-real-key\n")
        with tarfile.open(bad, "w:gz") as tar:
            tar.add(secret, arcname="secrets.env")
        proc = _run("--restore", bad, "--into", os.path.join(self.tmp, "fresh"))
        self.assertNotEqual(0, proc.returncode)
        self.assertIn("never backed up", proc.stderr)
        self.assertNotIn("zz-not-a-real-key", proc.stdout + proc.stderr,
                         "the refusal printed the value it was refusing")


class ShippingOffHostRefusesWithBothNames(_Estate):

    def setUp(self):
        super().setUp()
        _run("--backup", "--state-dir", self.state, "--into", self.into)
        self.archive = self._archives()[0]

    def test_it_refuses_while_both_values_are_unset(self):
        proc = _run("--ship", self.archive)
        self.assertEqual(2, proc.returncode)
        self.assertIn("REFUSING to ship", proc.stderr)
        self.assertIn("BACKUP_TARGET", proc.stderr)
        self.assertIn("BACKUP_ENCRYPTION", proc.stderr)
        self.assertIn("Nothing was sent", proc.stderr)

    def test_a_target_without_encryption_still_refuses(self):
        """The 6b decision is open. A destination is not permission to send
        300 real companies there in the clear."""
        proc = _run("--ship", self.archive,
                    env={"BACKUP_TARGET": "backup.example.invalid:/srv"})
        self.assertEqual(2, proc.returncode)
        self.assertIn("BACKUP_ENCRYPTION", proc.stderr)
        self.assertIn("not ours to publish", proc.stderr)

    def test_encryption_without_a_target_still_refuses(self):
        proc = _run("--ship", self.archive,
                    env={"BACKUP_ENCRYPTION": "age"})
        self.assertEqual(2, proc.returncode)
        self.assertIn("BACKUP_TARGET", proc.stderr)

    def test_with_both_set_it_still_sends_nothing_and_says_why(self):
        """The transport depends on what the target turns out to be. Writing
        an scp call against a guessed shape is how the guess becomes the
        design."""
        proc = _run("--ship", self.archive,
                    env={"BACKUP_TARGET": "backup.example.invalid:/srv",
                         "BACKUP_ENCRYPTION": "age"})
        self.assertEqual(3, proc.returncode)
        self.assertIn("Nothing was sent", proc.stderr)


if __name__ == "__main__":
    unittest.main()
