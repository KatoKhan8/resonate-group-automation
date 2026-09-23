#!/usr/bin/env python3
"""Register the cold start to run at logon. Prints by default, installs on ask.

THE GAP THIS CLOSES. `docs/MACHINE-HARDENING-2026-09-23.md` hardened the
machine against restarting and then said the quiet part: none of it survives a
restart that happens anyway. On 2026-09-23 the machine was back in three
minutes and the monitors were down for four hours, because bringing them back
is a person typing.

WHAT IT REGISTERS. One Scheduled Task, at logon, running

    <python> -m scripts.cold_start --start

`cold_start` clears the locks that provably predate the boot, refuses if a
supervisor is already up, and hands over to `src/supervisor.py`, which owns
starting and restarting. Nothing here spawns a monitor: two things that can
start a monitor is how two copies of one end up running.

NO ELEVATION. A logon-triggered task for the current user needs no admin
rights, which matters because §7 of the hardening doc is still waiting on an
elevated shell and this must not join that queue.

AT LOGON, NOT AT BOOT, and it is a real limitation rather than an oversight:
an at-boot task would run as SYSTEM, in a different profile, without the
user's environment - and `config/.env` lives in the user's checkout. The cost
is that an unattended reboot recovers when somebody logs in. With Windows set
to restart and sign back in automatically that is the same moment; without it,
it is not. Stated here so nobody discovers it during an incident.

THE LINUX FORM IS PRINTED TOO, unregistered, because the server migration
(increment F) replaces this file with a systemd unit and the unit should be
written from the command that is actually known to work.

    py -3 -m scripts.install_autostart              # show what would be done
    py -3 -m scripts.install_autostart --install
    py -3 -m scripts.install_autostart --status
    py -3 -m scripts.install_autostart --uninstall
"""
import argparse
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

TASK_NAME = "ResonateColdStart"

SYSTEMD_UNIT = """\
# /etc/systemd/system/resonate-supervisor.service   (increment F)
[Unit]
Description=Resonate monitor supervisor
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=%(user)s
WorkingDirectory=%(root)s
ExecStart=%(python)s -m scripts.cold_start --start
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
"""


def command():
    """The command the task runs. `sys.executable`, never `py -3`.

    `py -3` is a Windows launcher shim that does not exist on Linux, and the
    supervisor already resolves its children the same way for the same reason:
    this has to survive the server migration unchanged.
    """
    return [sys.executable, "-m", "scripts.cold_start", "--start"]


def install_argv():
    """The `schtasks` invocation, as a list, so it can be shown and asserted.

    /RL LIMITED, not HIGHEST: this needs no elevation and asking for it would
    make the task fail to register for a non-admin user rather than degrade.
    /F replaces an existing registration, so re-running is idempotent.
    """
    return ["schtasks", "/Create", "/TN", TASK_NAME, "/SC", "ONLOGON",
            "/RL", "LIMITED", "/F", "/TR",
            " ".join(('"%s"' % c) if " " in c else c for c in command())]


def systemd_unit():
    return SYSTEMD_UNIT % {
        "user": os.environ.get("USER") or os.environ.get("USERNAME") or "root",
        "root": ROOT,
        "python": sys.executable,
    }


def _run(argv):
    try:
        p = subprocess.run(argv, capture_output=True, text=True)
    except OSError as exc:                                      # noqa: BLE001
        return 1, "", str(exc)
    return p.returncode, (p.stdout or "").strip(), (p.stderr or "").strip()


def status():
    if os.name != "nt":
        return {"platform": "posix", "registered": None,
                "note": "systemd unit, not registered by this script"}
    rc, out, err = _run(["schtasks", "/Query", "/TN", TASK_NAME])
    return {"platform": "windows", "registered": rc == 0,
            "detail": out or err}


def main(argv=None):
    p = argparse.ArgumentParser(
        description="Register the cold start to run at logon.")
    p.add_argument("--install", action="store_true")
    p.add_argument("--uninstall", action="store_true")
    p.add_argument("--status", action="store_true")
    args = p.parse_args(argv)

    if args.status:
        st = status()
        for key in sorted(st):
            print("%-12s %s" % (key, st[key]))
        return 0 if st.get("registered") else 1

    if os.name != "nt":
        print("Not Windows. The systemd unit for increment F:\n")
        print(systemd_unit())
        return 0

    if args.uninstall:
        rc, out, err = _run(["schtasks", "/Delete", "/TN", TASK_NAME, "/F"])
        print(out or err)
        return rc

    if args.install:
        rc, out, err = _run(install_argv())
        print(out or err)
        if rc == 0:
            print("\nRegistered. It runs at logon as the current user and "
                  "needs no elevation.")
            print("Verify with:  py -3 -m scripts.install_autostart --status")
        return rc

    print("Would register scheduled task %r running:\n" % TASK_NAME)
    print("    " + " ".join(install_argv()))
    print("\nNothing was registered. Re-run with --install.")
    print("\nFor increment F, the same command as a systemd unit:\n")
    print(systemd_unit())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
