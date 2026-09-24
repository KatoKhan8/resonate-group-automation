"""Fourteen bison watchers were appending to one file.

`start_monitors.spawn` named the log after the SCRIPT —
`w-{basename(argv[0])}.out` — and every campaign watcher runs the same
`scripts/bison_watch_loop.py`. So 451, 481, 484, 485, 487, 489 and 491–498
all opened `w-bison_watch_loop.py.out` in append mode, fourteen processes
interleaving into one handle, with nothing in a line saying which campaign
wrote it.

The cost is paid exactly when the file is needed. 497 is where the blank
emails were found, by a person reading logs; separating one campaign's lines
out of a shared file while thirteen others write into it is the difference
between a log and a pile. Campaign watchers are also the monitors most
likely to be read one at a time, because an incident is about one campaign.
"""
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import start_monitors  # noqa: E402


class EachWatcherWritesItsOwnFile(unittest.TestCase):

    def test_two_bison_watchers_do_not_share_a_log(self):
        """The defect itself. Both run the same script; only the monitor
        name tells them apart."""
        a = start_monitors.log_path("bison_watch_497")
        b = start_monitors.log_path("bison_watch_498")
        self.assertNotEqual(a, b)

    def test_the_log_is_named_after_the_monitor_not_the_script(self):
        path = start_monitors.log_path("bison_watch_497")
        self.assertIn("bison_watch_497", os.path.basename(path))
        self.assertNotIn("bison_watch_loop.py", os.path.basename(path))

    def test_every_monitor_in_the_table_gets_a_distinct_path(self):
        """Asserted across the WHOLE derived table rather than two examples:
        a collision anywhere is the same defect, and the table is derived so
        it changes without anyone editing this test."""
        rows = [{"campaign_id": "c%d" % cid, "status": "approved",
                 "bison_campaign_id": cid}
                for cid in (451, 481, 484, 485, 487, 489, 491, 492, 493,
                            494, 495, 496, 497, 498)]
        from src import supervisor
        names = [m["name"] for m in supervisor.monitors(
            rows=rows, sequence_source=lambda p, c: 0)]
        paths = [start_monitors.log_path(n) for n in names]
        self.assertEqual(len(paths), len(set(paths)),
                         "two monitors share a log file")
        self.assertGreaterEqual(len(names), 15)

    def test_a_name_that_would_escape_the_directory_is_made_safe(self):
        """The name reaches a filesystem path. A monitor called `../x` must
        not write outside `work/`."""
        path = start_monitors.log_path("../../etc/passwd")
        self.assertEqual(os.path.dirname(os.path.abspath(path)),
                         os.path.abspath(start_monitors.WORK))
        self.assertNotIn("..", os.path.basename(path))

    def test_spawn_actually_opens_a_per_monitor_file(self):
        """THE GAP A MUTATION FOUND. The tests above call `log_path` directly,
        so reverting the fix INSIDE `spawn` - back to naming the file after
        `argv[0]` - left every one of them green. The call sites still read
        `spawn(argv, name)`, so the source check below passed too.

        So this drives `spawn` itself, with the process creation stubbed out,
        and reads the path off the handle it actually opened."""
        opened = []

        class FakePopen:
            def __init__(self, *a, **kw):
                opened.append(kw["stdout"].name)
                kw["stdout"].close()
                self.pid = 1234

        real = start_monitors.subprocess.Popen
        start_monitors.subprocess.Popen = FakePopen
        try:
            argv = ["scripts/bison_watch_loop.py", "--campaign", "497"]
            start_monitors.spawn(argv, "bison_watch_497")
            start_monitors.spawn(argv, "bison_watch_498")
        finally:
            start_monitors.subprocess.Popen = real

        self.assertEqual(2, len(opened))
        self.assertNotEqual(opened[0], opened[1],
                            "spawn opened one shared file for two monitors")
        self.assertIn("bison_watch_497", os.path.basename(opened[0]))
        self.assertIn("bison_watch_498", os.path.basename(opened[1]))
        for path in opened:
            if os.path.exists(path):
                os.unlink(path)

    def test_spawn_passes_the_monitor_name(self):
        """The fix is only real if the caller uses it. Asserted on the
        signature and on the call sites' source, because spawning a real
        process here would start a watcher."""
        import inspect
        sig = inspect.signature(start_monitors.spawn)
        self.assertIn("name", sig.parameters)
        source = inspect.getsource(start_monitors)
        self.assertNotIn("spawn(argv)\n", source,
                         "a call site still spawns without the monitor name")


if __name__ == "__main__":
    unittest.main()
