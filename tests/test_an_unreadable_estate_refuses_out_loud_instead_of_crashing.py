"""A git call the dating instrument depends on, failing, REFUSES out loud.

webapp/0420 measured the old failure mode and webapp/0440 repaired it;
webapp/0450 proved the repair in both directions. This module is the part that
makes the repair permanent, because nothing else in the tree notices if it goes
away: `safe_dating.git()` returned `(None, stderr)` for every failed git call,
and all seven call sites outside the module index `[0]` and use the result, so
an unreadable repository surfaced far from its cause as

    AttributeError: 'NoneType' object has no attribute 'decode'

at `run_arms.py:218` - zero controls evaluated, no verdict line, which is
indistinguishable from an instrument that never ran. The repair prints a named
refusal ending in `VERDICT: REFUSED-GIT-CALL-FAILED` and exits 1.

WHY THE FIXTURE IS SHAPED THE WAY IT IS. `git()` is only reachable once
`_resolve_estate` has ACCEPTED a directory, and it accepts on two tests only:
`os.path.isdir(path)` and `os.path.exists(path/.git)`. So a directory that
satisfies both and in which every git call still fails is a `.git` that EXISTS
and POINTS NOWHERE - the shape a linked worktree has after its administrative
directory is gone, since a linked worktree's `.git` is a FILE holding a
`gitdir:` line. That is 111 bytes of synthetic text and it is built here, at
test time, in a scratch temp directory: a 64-byte `.git` file whose `gitdir:`
target is a name that exists on no machine, and a 47-byte `synthetic.py`
holding one constant. No real worktree is pruned, no real repository path
appears in the fixture, and git does not walk up out of a dangling `gitdir:`
file, so the fixture behaves the same wherever the temp directory lives -
measured, including nested inside a real repository.

The byte counts are asserted rather than assumed, so a fixture that drifts in
shape fails loudly instead of quietly testing something else.

WHAT IS DERIVED RATHER THAN RETYPED. The exit code and git's own stderr are
measured live against the same fixture and compared with what the refusal
prints, so this module cannot pass by agreeing with a constant that has gone
stale. The call-site line number is read out of the driver, after asserting the
call appears there exactly once, so a reflow of `run_arms.py` moves the
expectation with it instead of turning a working refusal red.

THE INSTRUMENT IS COPIED INTO SCRATCH BEFORE IT IS RUN. `run_arms.py` builds
its own synthetic fixture repository in the directory the driver lives in, so
running it out of the tree would leave `tools/safe_dating_check/fixture-repo/`
behind as untracked state. The two modules are byte-copied into the temp
directory and run from there; `-B` and `PYTHONDONTWRITEBYTECODE` keep the copy
from writing bytecode next to it.
"""
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INSTRUMENT_DIR = os.path.join(ROOT, "tools", "safe_dating_check")
DRIVER = "run_arms.py"
MODULE = "safe_dating.py"

# The fixture, byte-exactly. The `gitdir:` target is relative and deliberately
# unremarkable: a relative target keeps the file a FIXED 64 bytes on every
# machine, which is what makes the 111-byte assertion below meaningful.
GITDIR_TARGET = "no-such-admin-dir-webapp-0470-absent-from-every-machine"
DOT_GIT_BYTES = ("gitdir: %s\n" % GITDIR_TARGET).encode("ascii")
SYNTHETIC_BYTES = b'SYNTHETIC = "no real data of any kind in here"\n'
DOT_GIT_SIZE = 64
SYNTHETIC_SIZE = 47
FIXTURE_SIZE = 111

VERDICT_MARK = "VERDICT:"
REFUSAL_VERDICT = "VERDICT: REFUSED-GIT-CALL-FAILED"
TRACEBACK_MARK = "Traceback (most recent call last):"
# The one call in the driver whose `None` the old contract handed back.
CALL_SITE_SOURCE = 'git(ESTATE, ["rev-parse", "HEAD"])'
CALL_SITE_FUNCTION = "arm_a"


def _force_writable(func, path, exc):
    """git writes loose objects read-only; rmtree needs them writable here."""
    os.chmod(path, 0o700)
    func(path)


def _remove_tree(path):
    if os.path.isdir(path):
        shutil.rmtree(path, onexc=_force_writable)


def _clean_git_env():
    """A copy of the environment with every GIT_CONFIG* override dropped, so
    whatever the caller's shell pinned cannot change what git reads here."""
    env = dict(os.environ)
    for name in list(env):
        if name.startswith("GIT_CONFIG"):
            del env[name]
    return env


def _build_fixture(tmp):
    """The 111-byte synthetic pruned worktree. Returns its absolute path."""
    estate = os.path.join(tmp, "dangling-estate")
    os.makedirs(estate)
    with io.open(os.path.join(estate, ".git"), "wb") as handle:
        handle.write(DOT_GIT_BYTES)
    with io.open(os.path.join(estate, "synthetic.py"), "wb") as handle:
        handle.write(SYNTHETIC_BYTES)
    return os.path.abspath(estate)


def _copy_instrument(tmp):
    """Byte-copy the driver and the module under test into scratch."""
    instrument = os.path.join(tmp, "instrument")
    os.makedirs(instrument)
    for name in (DRIVER, MODULE):
        shutil.copyfile(os.path.join(INSTRUMENT_DIR, name),
                        os.path.join(instrument, name))
    return instrument


def _probe_git(estate):
    """Run the instrument's first git call ourselves, so the exit code and the
    stderr the refusal is required to quote are MEASURED, not retyped."""
    proc = subprocess.run(
        ["git", "-C", estate, "rev-parse", "HEAD"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=_clean_git_env(),
    )
    return proc.returncode, proc.stderr.decode("utf-8", "replace").strip()


def _run_instrument(instrument, estate):
    env = _clean_git_env()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        [sys.executable, "-B", os.path.join(instrument, DRIVER),
         "--estate", estate],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        cwd=instrument, env=env,
    )
    return (proc.returncode,
            proc.stdout.decode("utf-8", "replace"),
            proc.stderr.decode("utf-8", "replace"))


def _call_site_line():
    """The 1-based line of the driver's `rev-parse HEAD` call, read from the
    file. Asserted unique by the caller: two matches would make the line
    number a guess between them."""
    with io.open(os.path.join(INSTRUMENT_DIR, DRIVER), encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    hits = [i + 1 for i, line in enumerate(lines) if CALL_SITE_SOURCE in line]
    return hits


class AnUnreadableEstateRefusesOutLoud(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="webapp-0470-dangling-")
        cls.addClassCleanup(_remove_tree, cls.tmp)
        cls.estate = _build_fixture(cls.tmp)
        cls.instrument = _copy_instrument(cls.tmp)
        cls.git_rc, cls.git_stderr = _probe_git(cls.estate)
        cls.rc, cls.out, cls.err = _run_instrument(cls.instrument, cls.estate)
        cls.combined = cls.out + cls.err

    # -- the fixture itself -------------------------------------------------

    def test_the_fixture_is_111_bytes_of_synthetic_text(self):
        """A .git FILE, not a directory, and the exact byte counts webapp/0450
        recorded - so a drift in the fixture's shape is a failure rather than a
        silent change of subject."""
        dot_git = os.path.join(self.estate, ".git")
        self.assertTrue(os.path.isfile(dot_git),
                        ".git must be a FILE: that is what a linked worktree "
                        "has, and a directory would be a real repository")
        self.assertFalse(os.path.isdir(dot_git))
        self.assertEqual(os.path.getsize(dot_git), DOT_GIT_SIZE)
        with io.open(dot_git, "rb") as handle:
            body = handle.read()
        self.assertEqual(body, DOT_GIT_BYTES)
        self.assertEqual(len(body.splitlines()), 1,
                         "one gitdir: line and nothing else")
        self.assertTrue(body.startswith(b"gitdir: "))
        synthetic = os.path.join(self.estate, "synthetic.py")
        self.assertEqual(os.path.getsize(synthetic), SYNTHETIC_SIZE)
        total = sum(os.path.getsize(os.path.join(self.estate, name))
                    for name in sorted(os.listdir(self.estate)))
        self.assertEqual(sorted(os.listdir(self.estate)),
                         [".git", "synthetic.py"])
        self.assertEqual(total, FIXTURE_SIZE)

    def test_the_gitdir_target_exists_nowhere(self):
        """The dangle is the whole point: a target that resolved would make
        this a working repository and the test would prove nothing."""
        self.assertFalse(os.path.exists(os.path.join(self.estate,
                                                     GITDIR_TARGET)))
        self.assertFalse(os.path.exists(GITDIR_TARGET))

    def test_the_fixture_is_accepted_as_an_estate_and_then_fails_git(self):
        """The positive control that the fixture still REACHES the repaired
        code. It satisfies both of `_resolve_estate`'s tests, so the resolver
        does not refuse it, and every git call inside it then fails."""
        self.assertTrue(os.path.isdir(self.estate))
        self.assertTrue(os.path.exists(os.path.join(self.estate, ".git")))
        self.assertNotEqual(self.git_rc, 0,
                            "a readable estate would not exercise the "
                            "failure path at all")
        self.assertNotIn("is not a git work tree", self.combined,
                         "a refusal from _resolve_estate would mean the git() "
                         "failure path was never reached")
        self.assertIn("estate repo :", self.combined,
                      "the run must get as far as arm (a)")

    # -- the two halves of the recorded post-repair signature ---------------

    def test_exactly_one_verdict_line_and_it_is_the_named_refusal(self):
        """webapp/0450's recorded post-repair half: 1 VERDICT line."""
        verdict_lines = [line for line in self.combined.splitlines()
                         if VERDICT_MARK in line]
        self.assertEqual(len(verdict_lines), 1,
                         "expected exactly one VERDICT line, got %r"
                         % (verdict_lines,))
        self.assertEqual(verdict_lines[0].strip(), REFUSAL_VERDICT)

    def test_no_traceback_reaches_the_operator(self):
        """webapp/0450's other recorded post-repair half: 0 tracebacks. The
        crash this replaces named neither the git command nor the repository,
        so its absence is the repair and its presence is the regression."""
        self.assertEqual(self.combined.count(TRACEBACK_MARK), 0,
                         "the failure path must not propagate a None into a "
                         "caller; it refuses at the point of failure")
        self.assertNotIn("AttributeError", self.combined)
        self.assertNotIn("'NoneType' object has no attribute", self.combined)

    # -- what the refusal has to say ----------------------------------------

    def test_the_refusal_quotes_the_command_repo_exit_code_and_git_stderr(self):
        """Every one of these was absent from the crash it replaces, and the
        exit code and stderr are compared against a LIVE probe of the same
        fixture rather than against a constant."""
        self.assertIn("  command    : git -C <repo> rev-parse HEAD",
                      self.combined)
        self.assertIn("  repo       : %s" % self.estate, self.combined)
        self.assertIn("  exit code  : %d" % self.git_rc, self.combined)
        self.assertTrue(self.git_stderr,
                        "git said nothing, so quoting it would prove nothing")
        self.assertIn("  git stderr : %s" % self.git_stderr, self.combined)

    def test_the_refusal_names_the_call_site_the_none_would_have_reached(self):
        """Derived from the driver, not retyped: the line number moves with a
        reflow instead of turning a working refusal red."""
        hits = _call_site_line()
        self.assertEqual(len(hits), 1,
                         "%r must appear exactly once in %s; got lines %r"
                         % (CALL_SITE_SOURCE, DRIVER, hits))
        self.assertIn("  call site  : %s() at %s:%d"
                      % (CALL_SITE_FUNCTION, DRIVER, hits[0]),
                      self.combined)

    def test_it_exits_nonzero_and_reports_no_controls_at_all(self):
        """Zero controls is the right answer and is unchanged by the repair:
        the estate is unreadable, so no control can honestly be evaluated
        against it. What changed is that the instrument now says so. This
        asserts the instrument never claims a verdict it did not earn."""
        self.assertEqual(self.rc, 1)
        self.assertNotIn("SAFE-CHECK-BUILT", self.combined)
        self.assertNotIn("FIX-INCOMPLETE", self.combined)
        self.assertNotIn("CONTROLS:", self.combined)


if __name__ == "__main__":
    unittest.main()
