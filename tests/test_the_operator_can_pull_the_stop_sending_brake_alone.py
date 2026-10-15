#!/usr/bin/env python3
r"""The operator's card for the STOP-SENDING brake - TASK 0210.

Pilotcaps/0160 criterion 9 wanted "a kill switch the owner can operate
alone". This module is the card: the exact commands, the exact
observable, and the proof that both work as written. It runs alone,
without a lane:

    py -3 -m unittest tests.test_the_operator_can_pull_the_stop_sending_brake_alone -v

THE COMMANDS. No clone, no session, no service, no browser - a keyboard
and cmd (or PowerShell) is the whole requirement, because the brake must
work when the thing it is stopping is broken:

    PULL, cmd:         type nul > "C:\Users\Zvonimir\Desktop\resonate-ops\STOP-SENDING"
    PULL, PowerShell:  New-Item -ItemType File "C:\Users\Zvonimir\Desktop\resonate-ops\STOP-SENDING" -Force | Out-Null

    RELEASE, cmd:         del "C:\Users\Zvonimir\Desktop\resonate-ops\STOP-SENDING"
    RELEASE, PowerShell:  Remove-Item "C:\Users\Zvonimir\Desktop\resonate-ops\STOP-SENDING"

Any file at that path, however created, is the brake: the content is
never read, existence is the signal, and a directory there stops sends
too (the conservative reading of "something is at the path"). The path is
absolute and outside every checkout, so the same file brakes every clone
and no clone can shadow it with one of its own.

THE OBSERVABLE, from any clone (py -3 -c, paste as-is):

    py -3 -c "from src import haltfile
    try:
        haltfile.require_released()
        print('RELEASED - sends permitted')
    except haltfile.OperatorStop as e:
        print('BRAKE ON:', e)
        raise SystemExit(1)"

    BRAKE ON: STOP-SENDING is present at ...Delete the file to release it
    -> exit code 1. RELEASED - sends permitted -> exit code 0. The
    one-line probe `py -3 -c "from src import haltfile; haltfile.
    require_released()"` is the same question with a plainer face:
    silence and exit 0 when released, the refusal named in a traceback
    and exit 1 when pulled.

WHAT THE FILE DOES NOT STOP. Mail already queued at EmailBison: the
render is a snapshot, and a queued row goes out with the words it was
queued with - the whole lesson of the 76 blank emails. The provider-side
pause is a separate layer and stays the operator's. And pulling this
brake never disables another brake: bison.pause, bison.stop_lead,
heyreach.pause and heyreach.stop_lead are exempt, so the 481
blank-content watch keeps re-applying its own halt every 180 seconds
with the file present. Deleting the file releases the brake; it never
un-sends.

NO TEST HERE CREATES THE REAL FILE. The pull and release commands are
exercised against a THROWAWAY path - the identical command shape, a
different path. The real path is only ever read: the two verbatim
observables consult it, and the in-process comparison consults it. The
day the operator pulls the brake, the agreement test below still passes,
because it asserts that the observable TELLS THE TRUTH about whichever
state it finds, not that the state is released.

Born-red at HEAD (pre-0210): ImportError on `src.haltfile`, like the
other 0210 modules.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from src import haltfile  # noqa: E402

REAL = haltfile.STOP_SENDING_PATH

CMD_PULL = 'type nul > "{path}"'
CMD_RELEASE = 'del "{path}"'
PS_PULL = ('New-Item -ItemType File -Path "{path}" -Force | Out-Null')
PS_RELEASE = 'Remove-Item -Path "{path}"'

# The observable's body, shared by the card version (real path) and the
# temp version (STOP_SENDING_PATH patched to the throwaway).
OBSERVABLE_BODY = """try:
    haltfile.require_released()
    print("RELEASED - sends permitted")
except haltfile.OperatorStop as e:
    print("BRAKE ON:", e)
    raise SystemExit(1)
"""

CARD_OBSERVABLE = f"from src import haltfile\n{OBSERVABLE_BODY}"
ONE_LINE_PROBE = "from src import haltfile; haltfile.require_released()"


def run_cmd(line):
    # One string, not a list: list-form would quote `line` as a single
    # argument and cmd would go looking for a FILE named "type nul > ...".
    return subprocess.run(f"cmd /c {line}", capture_output=True, text=True)


def run_powershell(line):
    return subprocess.run(["powershell", "-NoProfile", "-Command", line],
                          capture_output=True, text=True)


def run_python(script):
    """`py -3 -c <script>` from this clone: -c puts the cwd on sys.path,
    so cwd=ROOT is what makes `from src import haltfile` resolve - the
    same way the card's command resolves it from any clone."""
    return subprocess.run([sys.executable, "-c", script], cwd=ROOT,
                          capture_output=True, text=True)


def temp_observable(path):
    body = "\n".join("    " + line if line else line
                     for line in OBSERVABLE_BODY.splitlines())
    return ('from unittest import mock\n'
            'from src import haltfile\n'
            f'with mock.patch.object(haltfile, "STOP_SENDING_PATH",\n'
            f'                       r"{path}"):\n'
            f'{body}\n')


class _CardBase(unittest.TestCase):

    def setUp(self):
        super().setUp()
        self.tmp = tempfile.mkdtemp(prefix="rga-brake-card-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.brake = os.path.join(self.tmp, "STOP-SENDING")


class ThePullAndReleaseCommands(_CardBase):
    """The card's exact command lines, run as written against a
    throwaway path. A command that has not been run is a guess."""

    def test_the_cmd_pull_creates_a_zero_byte_file(self):
        proc = run_cmd(CMD_PULL.format(path=self.brake))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(os.path.isfile(self.brake),
                        "the documented cmd pull line did not create the "
                        "file")
        self.assertEqual(os.path.getsize(self.brake), 0,
                         "the brake is a zero-byte file; the command "
                         "created something else")

    def test_the_powershell_pull_creates_a_zero_byte_file(self):
        self.assertTrue(shutil.which("powershell"),
                        "powershell.exe ships with Windows; its absence "
                        "here would mean this clone's machine is not the "
                        "machine the card was written for")
        proc = run_powershell(PS_PULL.format(path=self.brake))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(os.path.isfile(self.brake))
        self.assertEqual(os.path.getsize(self.brake), 0)

    def test_either_pull_over_a_present_file_leaves_it_a_brake(self):
        """Pulling twice is not an error state: -Force over an existing
        file keeps it a zero-byte brake, so a repeated command cannot
        half-create the brake and report success."""
        run_cmd(CMD_PULL.format(path=self.brake))
        proc = run_powershell(PS_PULL.format(path=self.brake))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(os.path.isfile(self.brake))
        self.assertEqual(os.path.getsize(self.brake), 0)

    def test_the_cmd_release_removes_the_file(self):
        run_cmd(CMD_PULL.format(path=self.brake))
        proc = run_cmd(CMD_RELEASE.format(path=self.brake))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertFalse(os.path.exists(self.brake),
                         "the documented cmd release line did not remove "
                         "the brake")

    def test_the_powershell_release_removes_the_file(self):
        run_powershell(PS_PULL.format(path=self.brake))
        proc = run_powershell(PS_RELEASE.format(path=self.brake))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertFalse(os.path.exists(self.brake))


class TheObservable(_CardBase):
    """The card's observable, both branches, against the throwaway path
    the commands above manage."""

    def test_with_the_file_present_it_names_the_refusal_and_exits_1(self):
        run_cmd(CMD_PULL.format(path=self.brake))
        proc = run_python(temp_observable(self.brake))
        self.assertEqual(proc.returncode, 1,
                         "a pulled brake must be a FAILED command, not a "
                         f"green one: {proc.stdout}{proc.stderr}")
        self.assertIn("BRAKE ON:", proc.stdout)
        self.assertIn("STOP-SENDING is present", proc.stdout,
                      "the observable must carry the brake's own words, "
                      "not a paraphrase")
        self.assertIn("Delete the file to release it", proc.stdout,
                      "the operator is told how to un-pull it")

    def test_with_no_file_it_prints_released_and_exits_0(self):
        proc = run_python(temp_observable(self.brake))
        self.assertEqual(proc.returncode, 0,
                         f"{proc.stdout}{proc.stderr}")
        self.assertIn("RELEASED - sends permitted", proc.stdout)


class TheCardWorksFromThisCloneRightNow(_CardBase):
    """The card's commands VERBATIM - unpatched, real path, read-only.

    The assertion is AGREEMENT, not state: whatever the real path holds
    right now, the observable must say exactly what an in-process
    `require_released()` says. That is why this test does not flip the
    day the operator pulls the brake - it gets MORE interesting, not
    wrong: the card keeps telling the truth in both states. (The two
    reads are milliseconds apart; only a pull landing between them could
    disagree, and the next run would agree again.)"""

    def _in_process_verdict(self):
        try:
            haltfile.require_released()
        except haltfile.OperatorStop:
            return "refused"
        return "released"

    def test_the_card_observable_agrees_with_the_brake_itself(self):
        proc = run_python(CARD_OBSERVABLE)
        verdict = self._in_process_verdict()
        if verdict == "refused":
            self.assertEqual(
                proc.returncode, 1,
                f"the brake is pulled and the card's observable exited 0: "
                f"{proc.stdout}{proc.stderr}")
            self.assertIn("BRAKE ON:", proc.stdout)
        else:
            self.assertEqual(
                proc.returncode, 0,
                f"the brake is not pulled and the card's observable "
                f"exited nonzero: {proc.stdout}{proc.stderr}")
            self.assertIn("RELEASED - sends permitted", proc.stdout)

    def test_the_one_line_probe_agrees_too(self):
        proc = run_python(ONE_LINE_PROBE)
        verdict = self._in_process_verdict()
        if verdict == "refused":
            self.assertEqual(proc.returncode, 1)
            self.assertIn("OperatorStop", proc.stderr,
                          "the probe's observable is the traceback naming "
                          "the operator's stop")
        else:
            self.assertEqual(proc.returncode, 0,
                             f"{proc.stdout}{proc.stderr}")


if __name__ == "__main__":
    unittest.main()
