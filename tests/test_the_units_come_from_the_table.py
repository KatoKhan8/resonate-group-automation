"""2b — the systemd unit is generated, and it is generated from the table.

The unit is a file this repository writes and a Linux host executes, and
nothing between the two will tell us it is wrong. `systemctl start` on a bad
`ExecStart` fails at cutover, in the evening, on the one night the estate is
supposed to come up. So the checks that a person would otherwise do by
reading carefully are done here instead.

WHAT THESE ARE ACTUALLY GUARDING, in order of how expensive the mistake is:

  1. A WINDOWS PATH IN THE UNIT. This is authored on Windows and runs on
     Linux. `sys.executable` here is a `C:\\...` path, and a unit carrying
     one generates cleanly, commits cleanly, and dies at `systemctl start`
     naming a path nobody on the host recognises. Defect 4f's shape exactly:
     the symptom names neither the machine the file came from nor the line.

  2. CRLF. `.gitattributes` pins `*.service` to LF in the working tree
     because the working tree is what reaches the host, and a Python
     `write_text` on Windows re-introduces CRLF by default. This asserts the
     bytes, not the intent.

  3. A UNIT GENERATED FROM AN EMPTY TABLE. `campaigns.load()` answers an
     absent registry with an empty snapshot, so a generator that shrugged
     would emit a valid unit for an estate with no campaign watchers, start
     it, and report healthy. It must refuse.

  4. THE ONE-UNIT DECISION ITSELF. See `scripts/server/generate_units.py`:
     units written at deploy time freeze a table that is derived precisely
     so it does not freeze. If somebody later generates one unit per
     monitor, `test_no_per_monitor_units_are_written` fails and points at
     the reason rather than at a style preference.
"""
import io
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

GENERATOR = os.path.join(ROOT, "scripts", "server", "generate_units.py")

#: A registry the generator can derive a table from without reading `work/`.
#: Provider ids and statuses only - no client, name, address or contact.
FIXTURE_ROWS = [
    '{"campaign_id": "c497", "status": "approved", "bison_campaign_id": 497}',
    '{"campaign_id": "c498", "status": "approved", "bison_campaign_id": 498}',
    '{"campaign_id": "hr", "status": "approved", '
    '"heyreach_campaign_id": 605732}',
]


def _registry(tmp):
    path = os.path.join(tmp, "campaigns.jsonl")
    with io.open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(FIXTURE_ROWS) + "\n")
    return path


def _run(args, campaigns=None):
    """Run the generator in its own process, as the host would."""
    env = dict(os.environ)
    if campaigns:
        env["CAMPAIGNS"] = campaigns
    else:
        env.pop("CAMPAIGNS", None)
        # Point the whole state directory somewhere empty so the absent
        # registry is a real absence and not this developer's `work/`.
        env["QUEUE"] = os.path.join(tempfile.gettempdir(),
                                    "rga-units-no-registry", "queue.jsonl")
    return subprocess.run([sys.executable, GENERATOR] + args,
                          cwd=ROOT, env=env, capture_output=True, text=True)


class TheGeneratorRefusesRatherThanWatchingNothing(unittest.TestCase):

    def test_an_unreadable_registry_exits_2_and_writes_no_unit(self):
        tmp = tempfile.mkdtemp(prefix="rga-units-")
        out = os.path.join(tmp, "systemd")
        proc = _run(["--out-dir", out])
        self.assertEqual(2, proc.returncode, proc.stderr)
        self.assertIn("REFUSING", proc.stderr)
        self.assertFalse(os.path.exists(os.path.join(
            out, "resonate-supervisor.service")),
            "a unit was written despite the registry being unreadable")

    def test_the_refusal_says_what_would_have_happened(self):
        """A refusal that does not say what it prevented gets overridden by
        the next person in a hurry."""
        proc = _run(["--check"])
        self.assertIn("no campaign watchers", proc.stderr)


class TheUnitIsFitForALinuxHost(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-units-")
        self.out = os.path.join(self.tmp, "systemd")
        proc = _run(["--out-dir", self.out], campaigns=_registry(self.tmp))
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.unit_path = os.path.join(self.out, "resonate-supervisor.service")
        with io.open(self.unit_path, "rb") as fh:
            self.raw = fh.read()
        self.text = self.raw.decode("utf-8")

    def test_no_windows_path_reaches_the_unit(self):
        """The expensive one. `sys.executable` on this machine is a C:\\ path
        and the unit runs on Linux."""
        self.assertNotIn(b"\\", self.raw,
                         "a backslash reached a systemd unit")
        self.assertNotIn("C:", self.text)
        self.assertIn("ExecStart=/usr/bin/python3 -m scripts.supervise",
                      self.text)

    def test_the_unit_is_lf_only(self):
        """Asserted on the BYTES. A Python write_text on Windows
        re-introduces CRLF by default and the intent is not the file."""
        self.assertNotIn(b"\r\n", self.raw)

    def test_it_runs_the_supervisor_entry_point_that_exists(self):
        """`-m scripts.supervise` must name a real entry point, or the unit
        fails at start with ModuleNotFoundError."""
        self.assertTrue(os.path.exists(
            os.path.join(ROOT, "scripts", "supervise.py")))
        proc = subprocess.run(
            [sys.executable, "-m", "scripts.supervise", "--help"],
            cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(0, proc.returncode, proc.stderr)

    def test_the_secrets_file_is_the_one_provisioning_created(self):
        self.assertIn("EnvironmentFile=/etc/resonate/secrets.env", self.text)

    def test_it_stops_on_sigterm_with_room_to_stop_children(self):
        """A SIGKILLed supervisor leaves orphaned monitors holding their
        locks, and the next start finds every lock taken and watches
        nothing."""
        self.assertIn("KillSignal=SIGTERM", self.text)
        self.assertIn("TimeoutStopSec=", self.text)

    def test_the_restart_limit_is_neither_the_default_nor_unlimited(self):
        """The default gives up after 5 starts in 10s and leaves the unit
        `failed` - an estate that is down and looks configured. Unlimited
        crash-loops a broken deploy forever."""
        self.assertIn("Restart=always", self.text)
        self.assertIn("StartLimitBurst=10", self.text)
        self.assertIn("StartLimitIntervalSec=300", self.text)

    def test_the_app_directory_stays_writable_under_hardening(self):
        """`work/` is written by every monitor. Hardening that forgets it
        produces a supervisor that starts and then fails on first write."""
        self.assertIn("NoNewPrivileges=true", self.text)
        self.assertIn("ReadWritePaths=", self.text)


class TheUnitComesFromTheTable(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-units-")
        self.out = os.path.join(self.tmp, "systemd")
        proc = _run(["--out-dir", self.out], campaigns=_registry(self.tmp))
        self.assertEqual(0, proc.returncode, proc.stderr)
        with io.open(os.path.join(self.out, "MONITOR-TABLE.txt"),
                     encoding="utf-8") as fh:
            self.manifest = fh.read()

    def test_the_manifest_names_every_monitor_the_table_derives(self):
        from src import supervisor
        rows = [{"campaign_id": "c497", "status": "approved",
                 "bison_campaign_id": 497},
                {"campaign_id": "c498", "status": "approved",
                 "bison_campaign_id": 498}]
        for mon in supervisor.monitors(rows=rows,
                                       sequence_source=lambda p, c: 0):
            self.assertIn(mon["name"], self.manifest)

    def test_the_manifest_names_the_heartbeat_file_not_a_guess(self):
        """The 46474c6c defect, in the artifact a person reads at cutover: a
        manifest that guessed `<name>.json` would show a file nothing
        writes."""
        self.assertIn("heyreach-605732.json", self.manifest)
        self.assertIn("bison-497.json", self.manifest)

    def test_no_per_monitor_units_are_written(self):
        """THE DESIGN DECISION, pinned. One unit runs the estate and the
        supervisor derives the table on every tick. Units written per
        monitor at deploy time freeze a table that is derived precisely so
        it does not freeze - a campaign going live at noon would have no
        unit until somebody regenerated, which is the hand-written list
        again wearing systemd's clothes."""
        written = sorted(os.listdir(self.out))
        self.assertEqual(["MONITOR-TABLE.txt", "resonate-supervisor.service"],
                         written)

    def test_the_manifest_says_it_is_a_record_and_not_an_input(self):
        """Nothing reads it back. A generated file that looks like config is
        a file somebody will eventually edit expecting an effect."""
        self.assertIn("Not read by anything", self.manifest)


if __name__ == "__main__":
    unittest.main()
