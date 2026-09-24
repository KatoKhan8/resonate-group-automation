"""2c — deploy.sh deploys a tag, refuses a branch, and rolls back.

WHY THIS EXISTS AT ALL. `deploy.sh` has never been run against the host, by
design — the same standing as `provision.sh` before 2026-09-23, when running
it found six defects in a script that had been written and reviewed. Review
did not find them; execution did. So the parts that can be executed without a
host are executed here, against a throwaway repository in a temp directory.

**A ROLLBACK THAT HAS NEVER BEEN RUN IS NOT A ROLLBACK.** It is a section in
a script that has the word in it. The rollback path is exercised for real
below: deploy v1, deploy v2, roll back, and assert the tree is at v1 again
and the state file says so.

WHAT IS AND IS NOT COVERED. The git mechanics — tag verification, the branch
refusal, the dirty-tree refusal, checkout, the state file, the rollback and
the staging-copy removal — are all real here. The systemd half is not: this
machine has no systemd, so the tests pass `--skip-units`, which the script
ANNOUNCES rather than inferring. Installing and starting the unit is item 3,
on the host, and nothing here should be read as evidence about it.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEPLOY = os.path.join(ROOT, "scripts", "server", "deploy.sh")

BASH = shutil.which("bash")


def _bashpath(p):
    """`C:\\x\\y` -> `/c/x/y`, which is what Git Bash understands."""
    p = os.path.abspath(p).replace("\\", "/")
    if len(p) > 1 and p[1] == ":":
        p = "/" + p[0].lower() + p[2:]
    return p


def _git(cwd, *args):
    return subprocess.run(("git",) + args, cwd=cwd, capture_output=True,
                          text=True, check=True)


@unittest.skipUnless(BASH, "bash is not available on this machine")
class _DeployFixture(unittest.TestCase):
    """An origin with two tags and a branch, and a checkout sitting at v1."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-deploy-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.origin = os.path.join(self.tmp, "origin")
        self.app = os.path.join(self.tmp, "app")
        self.state = os.path.join(self.tmp, "state")
        self.staging = os.path.join(self.tmp, "suite-check")

        os.makedirs(self.origin)
        _git(self.origin, "init", "--quiet", "--initial-branch=master")
        _git(self.origin, "config", "user.email", "t@example.invalid")
        _git(self.origin, "config", "user.name", "t")
        for tag in ("v1", "v2"):
            with open(os.path.join(self.origin, "marker.txt"), "w",
                      encoding="utf-8", newline="\n") as fh:
                fh.write(tag + "\n")
            _git(self.origin, "add", "marker.txt")
            _git(self.origin, "commit", "--quiet", "-m", tag)
            _git(self.origin, "tag", tag)

        _git(self.tmp, "clone", "--quiet", self.origin, self.app)
        _git(self.app, "checkout", "--quiet", "--detach", "refs/tags/v1")

    def deploy(self, *args, expect=0):
        env = dict(os.environ)
        env.update(APP_DIR=_bashpath(self.app),
                   STATE_FILE=_bashpath(self.state),
                   STAGING_COPY=_bashpath(self.staging),
                   SECRETS_FILE=_bashpath(os.path.join(self.tmp, "secrets")))
        proc = subprocess.run(
            [BASH, _bashpath(DEPLOY), "--skip-units"] + list(args),
            cwd=self.tmp, env=env, capture_output=True, text=True)
        self.assertEqual(expect, proc.returncode,
                         "stdout:\n%s\nstderr:\n%s" % (proc.stdout, proc.stderr))
        return proc

    def marker(self):
        with open(os.path.join(self.app, "marker.txt"), encoding="utf-8") as fh:
            return fh.read().strip()

    def state_lines(self):
        with open(self.state, encoding="utf-8") as fh:
            return [l.strip() for l in fh if l.strip()]


class ItDeploysATagAndOnlyATag(_DeployFixture):

    def test_a_tag_is_checked_out(self):
        self.deploy("--tag", "v2")
        self.assertEqual("v2", self.marker())

    def test_a_branch_is_refused(self):
        """`git rev-parse master` resolves happily, which is exactly why the
        check has to ask for refs/tags/<name> explicitly. A branch deploys
        whatever it points at this second and leaves a rollback nothing to
        return to."""
        proc = self.deploy("--tag", "master", expect=1)
        self.assertIn("is not a tag", proc.stderr)
        self.assertEqual("v1", self.marker(), "the tree moved anyway")

    def test_a_tag_that_does_not_exist_is_refused(self):
        proc = self.deploy("--tag", "v99", expect=1)
        self.assertIn("is not a tag", proc.stderr)
        self.assertEqual("v1", self.marker())

    def test_no_tag_at_all_is_refused(self):
        proc = self.deploy(expect=1)
        self.assertIn("deploys a TAG, never a branch", proc.stderr)

    def test_check_mode_changes_nothing(self):
        self.deploy("--check", "--tag", "v2")
        self.assertEqual("v1", self.marker())
        self.assertFalse(os.path.exists(self.state))


class TheRollbackIsExercisedAndNotJustWritten(_DeployFixture):

    def test_a_rollback_returns_the_tree_to_the_previous_tag(self):
        self.deploy("--tag", "v2")
        self.assertEqual("v2", self.marker())
        self.deploy("--rollback")
        self.assertEqual("v1", self.marker(),
                         "the rollback did not restore the previous tag")

    def test_the_state_file_records_current_and_previous(self):
        self.deploy("--tag", "v2")
        lines = self.state_lines()
        self.assertEqual("v2", lines[0])
        self.assertEqual("v1", lines[1],
                         "the replaced ref was not recorded, so a rollback "
                         "would have nowhere to go")

    def test_a_rollback_with_no_previous_deploy_refuses(self):
        """A rollback that guesses is not a rollback."""
        proc = self.deploy("--rollback", expect=1)
        self.assertIn("no previous deploy to return to", proc.stderr)

    def test_the_state_file_lives_outside_the_checkout(self):
        """A state file inside the tree is one a `git checkout` can change
        underneath the script reading it."""
        self.deploy("--tag", "v2")
        self.assertFalse(
            os.path.abspath(self.state).startswith(os.path.abspath(self.app)))


class ItWillNotDiscardWorkSomebodyDidOnTheHost(_DeployFixture):

    def _dirty(self):
        with open(os.path.join(self.app, "marker.txt"), "w",
                  encoding="utf-8", newline="\n") as fh:
            fh.write("edited on the host at 23:00\n")

    def test_a_dirty_tree_is_refused_and_shown(self):
        """`git checkout` would silently destroy a change made by somebody
        who then goes to bed believing it is live."""
        self._dirty()
        proc = self.deploy("--tag", "v2", expect=1)
        self.assertIn("uncommitted changes", proc.stderr)
        self.assertIn("marker.txt", proc.stderr, "it refused without saying what")
        self.assertEqual("edited on the host at 23:00", self.marker(),
                         "the edit was destroyed despite the refusal")

    def test_force_discards_it_and_says_so(self):
        self._dirty()
        proc = self.deploy("--force", "--tag", "v2")
        self.assertEqual("v2", self.marker())
        self.assertIn("discarding uncommitted changes", proc.stdout)


class TheStagingCopyIsRemoved(_DeployFixture):

    def test_the_suite_check_directory_is_deleted(self):
        """Left by the 2026-09-23 suite run. No .git, no work/, no hosts/ —
        not a deployment, and nothing should deploy onto it or read it as
        the app."""
        os.makedirs(self.staging)
        with open(os.path.join(self.staging, "stale.txt"), "w",
                  encoding="utf-8") as fh:
            fh.write("x")
        self.deploy("--tag", "v2")
        self.assertFalse(os.path.exists(self.staging))

    def test_check_mode_does_not_delete_it(self):
        os.makedirs(self.staging)
        self.deploy("--check", "--tag", "v2")
        self.assertTrue(os.path.exists(self.staging))


if __name__ == "__main__":
    unittest.main()
