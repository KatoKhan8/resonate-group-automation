#!/usr/bin/env python3
"""Supervise every declared monitor.

    py -3 -m scripts.supervise              # run the supervisor
    py -3 -m scripts.supervise --status     # show monitor status

Foreground process, logs to stdout/stderr, SIGTERM stops children cleanly.
Ready for systemd. Does not daemonise, does not write its own pidfile.

THE INTERPRETER. The supervisor resolves it as `sys.executable`, not
`py -3`. This script is the entry point; the supervisor module does the
actual spawning.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import supervisor  # noqa: E402


def main():
    parser = argparse.ArgumentParser(
        description="Supervise every declared monitor")
    parser.add_argument("--status", action="store_true",
                        help="Show the status of every declared monitor "
                             "and exit")
    args = parser.parse_args()

    if args.status:
        print(supervisor.format_status(supervisor.MONITORS))
        return

    supervisor._run()


if __name__ == "__main__":
    main()
