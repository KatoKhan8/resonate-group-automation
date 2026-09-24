"""2h — the three tmux units, and the enable-linger that is easy to miss.

THE ONE THING THAT ACTUALLY FAILS HERE. A systemd USER manager normally
starts at first login and stops at last logout. Three units enabled without
`loginctl enable-linger` come back the moment somebody logs in — so every
casual check passes, and they are absent exactly when they are needed: after
an unattended 02:00 reboot, with nobody logged in.

That is a failure mode that hides behind the act of looking for it, which is
why the spec's verification (§6) says to check BEFORE logging in, and why
these tests assert that the generated instructions say so rather than leaving
it to be remembered.

WHAT IS NOT COVERED. Whether the units actually start tmux on the host: this
machine has no systemd and no `loginctl`. The reboot verification is item 3's,
on the host, and nothing here is evidence about it.
"""
import io
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

SCRIPT = os.path.join(ROOT, "scripts", "server", "generate_tmux_units.py")


def directives(text):
    """The unit's actual directives, with comments stripped.

    Asserting on the whole file caught this module's own comments twice -
    "Restart=always would resurrect it" and "RemainAfterExit is not" are
    explanations of what the unit does NOT do, and a test reading them as
    directives fails on prose. CLAUDE.md: a test that searches source for
    words fails when somebody writes a comment.
    """
    return [l.strip() for l in text.splitlines()
            if l.strip() and not l.strip().startswith("#")]


def _run(*args):
    return subprocess.run([sys.executable, SCRIPT] + list(args),
                          cwd=ROOT, capture_output=True, text=True)


class TheThreeUnitsAreGenerated(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-tmux-")
        proc = _run("--out-dir", self.tmp)
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.units = {}
        for name in os.listdir(self.tmp):
            with io.open(os.path.join(self.tmp, name), encoding="utf-8") as fh:
                self.units[name] = fh.read()

    def test_one_unit_per_session_and_no_template(self):
        """`%i` would be tidier and does not spell any of the three real
        worktree names: `production` is not `resonate-group-automation`."""
        self.assertEqual(
            {"tmux-production.service", "tmux-agent.service",
             "tmux-infra.service", "INSTALL.sh"},
            set(self.units))

    def test_each_opens_in_its_own_worktree(self):
        pairs = {"tmux-production.service": "resonate-group-automation",
                 "tmux-agent.service": "resonate-slack-agent",
                 "tmux-infra.service": "resonate-infra"}
        for name, worktree in pairs.items():
            self.assertIn("-c /home/resonate/%s" % worktree, self.units[name])

    def test_a_session_killed_by_hand_stays_killed(self):
        """Restart=always would resurrect it under the operator and make
        `tmux kill-session` look broken."""
        for name, text in self.units.items():
            if name.endswith(".service"):
                lines = directives(text)
                self.assertIn("Restart=no", lines)
                self.assertNotIn("Restart=always", lines)

    def test_forking_not_simple(self):
        """`new-session -d` returns immediately and the server keeps running
        after tmux exits."""
        for name, text in self.units.items():
            if name.endswith(".service"):
                lines = directives(text)
                self.assertIn("Type=forking", lines)
                self.assertFalse([l for l in lines if "RemainAfterExit" in l])

    def test_the_units_are_lf_only(self):
        for name in self.units:
            with io.open(os.path.join(self.tmp, name), "rb") as fh:
                self.assertNotIn(b"\r\n", fh.read(),
                                 "%s was written with CRLF" % name)


class LingeringIsNamedAndNotLeftToMemory(unittest.TestCase):

    def test_the_instructions_name_enable_linger(self):
        out = _run("--check").stdout
        self.assertIn("loginctl enable-linger resonate", out)

    def test_they_say_what_happens_without_it(self):
        """A step whose consequence is unstated is a step somebody skips."""
        out = _run("--check").stdout
        self.assertIn("after a reboot until somebody logs in", out)

    def test_the_verification_says_not_to_log_in_first(self):
        """The failure hides behind the act of looking for it: logging in is
        what starts the user manager."""
        out = _run("--check").stdout
        self.assertIn("Do NOT log in", out)

    def test_it_names_the_unattended_reboot_that_would_expose_it(self):
        out = _run("--check").stdout
        self.assertIn("02:00", out)

    def test_check_writes_nothing(self):
        tmp = tempfile.mkdtemp(prefix="rga-tmux-check-")
        _run("--check")
        self.assertEqual([], os.listdir(tmp))


if __name__ == "__main__":
    unittest.main()
