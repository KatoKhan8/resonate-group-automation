"""The provisioning script must survive the three things it does to itself.

All three were MEASURED ON THE HOST on 2026-09-23, on the first and second
real executions of `scripts/server/provision.sh`. Each one aborted the run,
and each one aborted it AFTER doing something irreversible-ish to the host,
which is why they are worth a test apiece rather than a fix apiece.

    1. `yes | ufw enable`  ->  exit 141, with the firewall already up
    2. no sudo password    ->  no administrative path, with root ssh already off
    3. systemd-timesyncd   ->  unit does not exist on 26.04

THE SHAPE THEY SHARE is a step that takes something away before the thing
replacing it is known to work. Step 1 already gets this right on purpose -
the header explains at length why port 22 is allowed BEFORE `ufw enable` -
and the other two are the same mistake in places nobody had looked.

These tests read the PLAN the script emits under `--check`, not its source
text. The difference is not pedantic: the first version of the time-sync
test read the source, and the source still defines `$TIMECHECK` even when
the line that runs it has been changed back to the broken `systemctl
enable`. It passed against the restored bug. A test that cannot fail is
worse than no test, because it is believed.
"""
import re
import subprocess
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "server" / "provision.sh"
ANSI = re.compile(r"\x1b\[[0-9;]*m")


def _plan():
    """Run the script's own dry run and return its lines, colour stripped."""
    out = subprocess.run(
        ["bash", str(SCRIPT), "--check"],
        capture_output=True, text=True, timeout=120,
    )
    assert out.returncode == 0, f"--check exited {out.returncode}: {out.stderr}"
    return [ANSI.sub("", line).strip() for line in out.stdout.splitlines()]


def _run_lines():
    """The commands the plan will actually execute, in order."""
    return [l.split("WOULD:", 1)[1].strip() for l in _plan() if "WOULD:" in l]


class TestProvisionSurvivesItsOwnFirewall(unittest.TestCase):
    """`ufw enable` reads one line and exits. `yes` is then killed by SIGPIPE
    and the pipeline reports 141. Under `set -euo pipefail` that is an abort,
    one line after the firewall came up.

    WHY IT WAS INVISIBLE: enabling a firewall on a remote host looks exactly
    like a dropped connection - output stops mid-run. The natural reading is
    "ufw disrupted my ssh session", the natural next move is to reconnect and
    find the firewall correctly configured, and nothing anywhere mentions the
    seven steps that never ran. Reconnecting proves the firewall works. It
    proves nothing about the rest of the script.
    """

    @classmethod
    def setUpClass(cls):
        cls.commands = _run_lines()
        cls.text = SCRIPT.read_text(encoding="utf-8")

    def test_the_script_still_runs_under_pipefail(self):
        """The premise every other test here rests on. If this stops being
        true, 141 stops being an abort and these tests are about a different
        script."""
        self.assertIn("set -euo pipefail", self.text)

    def test_ufw_is_enabled_without_a_pipeline(self):
        enables = [c for c in self.commands if "ufw" in c and "enable" in c]
        self.assertEqual(
            len(enables), 1, f"expected exactly one ufw enable, got {enables}"
        )
        self.assertNotIn(
            "|", enables[0],
            "ufw enable is piped into. `yes | ufw enable` exits 141 under "
            "pipefail and aborts the script with the firewall already up. "
            "Use `ufw --force enable`.",
        )
        self.assertIn("--force", enables[0])

    def test_no_executed_line_feeds_a_command_that_stops_reading(self):
        """`yes` is the one that bit. Any generator feeding a consumer that
        exits early carries the same 141."""
        offenders = [
            c for c in self.commands
            if "|" in c and re.match(r"^(yes|seq|printf|echo)\b", c.split("|")[0].strip())
        ]
        self.assertEqual(
            offenders, [],
            "these pipe a generator into a consumer that may stop reading; "
            f"under pipefail that is an abort, not a warning: {offenders}",
        )

    def test_the_firewall_step_is_still_first(self):
        """Not about the pipeline - about what the abort exposed. Step 1
        running alone was survivable only because step 1 is the firewall."""
        steps = [l for l in _plan() if l.startswith("== ")]
        self.assertTrue(steps[0].startswith("== 1."), steps[:2])
        self.assertIn("FIREWALL FIRST", steps[0])


class TestTheAdministrativePathOutlivesRootLogin(unittest.TestCase):
    """MEASURED ON THE HOST, the run after the ufw fix. Step 2b completed.

    Root ssh was off, the app user could log in - and could not sudo.
    `adduser --disabled-password` leaves no password, `%sudo ALL=(ALL:ALL)
    ALL` demands one, and /etc/sudoers.d was empty. Membership of the sudo
    group had bought nothing. The host had no administrative path at all and
    needed the provider's console.

    The note in step 2b saying "VERIFY A SECOND SSH SESSION AS <user> BEFORE
    CLOSING THE ONE YOU ARE IN" was already there, and did not help, because
    a second session as the app user SUCCEEDS. Logging in was never the part
    that broke. What breaks is the part the note does not mention.
    """

    @classmethod
    def setUpClass(cls):
        cls.plan = _plan()

    def _first(self, needle):
        for i, line in enumerate(self.plan):
            if needle in line:
                return i
        self.fail(f"the plan never mentions {needle!r}")

    def test_sudo_access_is_granted_before_root_login_is_removed(self):
        # "WOULD write", not merely a mention of the path: `visudo -c -f
        # /etc/sudoers.d/90-<user>` names the same file and is a CHECK of a
        # drop-in, not the writing of one. Matching the path alone let a
        # mutation that removed the write pass this test.
        grant = self._first("WOULD write /etc/sudoers.d/90-")
        remove = self._first("PermitRootLogin no")
        self.assertLess(
            grant, remove,
            "the sudoers drop-in must be written BEFORE root ssh is disabled",
        )

    def test_the_drop_in_is_syntax_checked(self):
        """A sudoers file with a syntax error is itself a lockout: sudo
        refuses to run at all rather than ignoring the bad file."""
        self.assertTrue(
            any("visudo -c" in l for l in self.plan),
            "the plan must validate the drop-in it writes",
        )

    def test_the_script_refuses_rather_than_trusting_the_grant(self):
        """Writing the drop-in is not the guarantee; proving it works is. A
        drop-in with a typo in the username parses fine and grants nothing."""
        verify = self._first("WOULD verify")
        remove = self._first("PermitRootLogin no")
        self.assertLess(verify, remove)
        self.assertTrue(
            any("REFUSE" in l for l in self.plan[verify:remove]),
            "the plan must say it will REFUSE to harden sshd if the "
            "administrative check fails, not merely that it will check",
        )

    def test_sudo_group_membership_is_not_relied_on_alone(self):
        """usermod -aG sudo is still correct and is still not sufficient."""
        text = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("usermod -aG sudo", text)
        self.assertIn("NOPASSWD", text)


class TestTimeSyncAsksForAClockNotAService(unittest.TestCase):
    """MEASURED ON THE HOST: step 3 ran `systemctl enable --now
    systemd-timesyncd` and failed with "Unit systemd-timesyncd.service does
    not exist", aborting the run.

    Ubuntu 26.04 does not ship systemd-timesyncd on this image - the package
    exists in the archive and is not installed. CHRONY is what ships, and it
    was ALREADY SYNCHRONISING. So the step failed while the condition it
    wanted was already satisfied. It also enabled a service in step 3 that
    step 4 had not yet had a chance to install.
    """

    @classmethod
    def setUpClass(cls):
        cls.plan = _plan()

    def _step_three(self):
        out, on = [], False
        for line in self.plan:
            if line.startswith("== 3."):
                on = True
                continue
            if on and line.startswith("== "):
                break
            if on:
                out.append(line)
        self.assertTrue(out, "the plan has no step 3")
        return out

    def test_no_step_enables_systemd_timesyncd(self):
        offenders = [
            c for c in _run_lines()
            if "systemd-timesyncd" in c and "enable" in c
            and "apt-get install" not in c
        ]
        self.assertEqual(
            offenders, [],
            "systemd-timesyncd is not on the 26.04 image; enabling it aborts "
            f"the run under set -e: {offenders}",
        )

    def test_the_clock_is_checked_before_anything_is_installed(self):
        executed = " ".join(l for l in self._step_three() if "WOULD" in l)
        self.assertIn(
            "NTPSynchronized", executed,
            "step 3 must ASK whether the clock is synchronised. Defining a "
            "variable that asks is not asking; the run line is what runs.",
        )
        self.assertLess(
            executed.index("NTPSynchronized"), executed.index("apt-get"),
            "step 3 must ask before it installs; on this image the clock is "
            "already synchronised by chrony and nothing needs installing",
        )


if __name__ == "__main__":
    unittest.main()
