#!/usr/bin/env python3
"""2b - generate the systemd units for the estate, FROM the monitor table.

    py -3 scripts/server/generate_units.py --check
    py -3 scripts/server/generate_units.py --out-dir build/systemd

ONE UNIT RUNS THE ESTATE, AND THAT IS THE DESIGN DECISION THIS FILE IS
ACCOUNTABLE FOR. The obvious reading of "units generated from the monitor
table" is one unit per monitor - `bison-497.service`, and so on. It is the
wrong shape here, for a reason this branch already paid for once:

**THE TABLE IS DERIVED, AND UNITS ARE NOT.** `supervisor.monitors()` is a
function rather than a constant precisely because a derived table computed
once freezes: `test_the_table_is_not_frozen_at_import` pins that. Units
written to disk at deploy time freeze it HARDER - a campaign that goes live
at noon would have no unit until somebody regenerated and ran
`daemon-reload`. That is the same failure as the hand-written list: a
campaign that can send and has nothing watching it, discovered by a person
noticing. Campaign 497 is what that costs.

`src/supervisor.py`'s own docstring says it is ready for systemd: foreground,
logs to stdout/stderr, SIGTERM stops children cleanly, no daemonising, no
pidfile. It already owns per-monitor locking (`singlewalker`), restart with
backoff (30s, doubling, 10-minute ceiling), heartbeat reading and
notification. Per-monitor units would put a SECOND restart policy next to
that one, and two restart policies for one process is how a monitor comes to
be running twice.

So: `resonate-supervisor.service` runs `python -m scripts.supervise`, and the
supervisor derives the table on every tick. A campaign launched at noon is
watched at noon, with no unit regenerated and no deploy.

WHAT IS THEN "GENERATED FROM THE TABLE"? The unit is generated - its
interpreter, its paths, its user, its environment file - and the table is
READ, validated, and written beside it as a manifest, so the cutover can see
what the estate will watch before it starts anything. The manifest is a
record, never an input: nothing reads it back.

THE GENERATOR REFUSES RATHER THAN EMITTING A UNIT THAT WATCHES NOTHING.
`campaigns.load()` answers an absent registry with an empty snapshot, so a
generator that shrugged would emit a perfectly valid unit for an estate with
no campaign watchers in it and report success. `supervisor.monitors()` raises
`RegistryUnreadable` for exactly that case and this script exits 2.
"""
import argparse
import datetime
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from src import supervisor  # noqa: E402

#: Where the deployed checkout lives on the host, matching `provision.sh`.
APP_USER = os.environ.get("APP_USER", "resonate")
APP_DIR = os.environ.get(
    "APP_DIR", "/home/%s/resonate-group-automation" % APP_USER)
SECRETS_FILE = "/etc/resonate/secrets.env"

#: The interpreter ON THE HOST. Not `sys.executable` - that is this machine's
#: Windows path, and writing it into a unit is how a unit that generates
#: cleanly fails at `systemctl start` with a path nobody recognises.
HOST_PYTHON = os.environ.get("HOST_PYTHON", "/usr/bin/python3")

SUPERVISOR_UNIT = "resonate-supervisor.service"
WEBHOOK_UNIT = "resonate-webhook.service"
#: Loopback only. Caddy terminates TLS in front of it and the
#: receiver must never be reachable directly.
WEBHOOK_PORT = 8787


def supervisor_unit(app_dir=APP_DIR, user=APP_USER, python=HOST_PYTHON):
    """The one unit. Hardened, and every non-obvious line carries its why."""
    return """\
[Unit]
Description=Resonate monitor supervisor
Documentation=file://%(app_dir)s/docs/SERVER-PACKAGE-2B-SYSTEMD-UNITS.md
# The network being "up" is not the network being usable, but the monitors
# all retry and none of them needs a provider inside the first second, so
# this is ordering and not a guarantee.
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=%(user)s
Group=%(user)s
WorkingDirectory=%(app_dir)s

# 640 root:%(user)s, written by 2d. systemd reads it as root BEFORE dropping
# to %(user)s, which is why the file does not need to be readable by the app
# user's shell.
EnvironmentFile=%(secrets)s

# `-m scripts.supervise`, not the file path: the module form is what sets
# sys.path the way the package expects, and it is the form the entry point
# documents.
ExecStart=%(python)s -m scripts.supervise

# Foreground, unbuffered, so journald gets each line as it happens rather
# than in 8 KB blocks when a monitor finally dies.
Environment=PYTHONUNBUFFERED=1

# SIGTERM is what `supervisor` handles: it stops children cleanly. Give it
# room to do that before systemd escalates to SIGKILL, because a killed
# supervisor leaves orphaned monitor processes holding their locks, and the
# next start then finds every lock taken and watches nothing.
KillSignal=SIGTERM
KillMode=mixed
TimeoutStopSec=90

Restart=always
RestartSec=10
# NOT unlimited, and not the default either. The default gives up after 5
# starts in 10s and leaves the unit `failed` - an estate that is down and
# looks configured. 0 disables the limit entirely, which crash-loops a
# genuinely broken deploy forever. This is wide enough that a transient
# fault always recovers and narrow enough that a broken one lands in
# `failed`, where `cold_start --verify` and `systemctl status` both say so.
StartLimitIntervalSec=300
StartLimitBurst=10

# Hardening. The supervisor spawns Python children and writes `work/` and
# nothing else.
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ProtectHome=false
ProtectKernelTunables=true
ProtectControlGroups=true
RestrictSUIDSGID=true
# ProtectSystem=full leaves /home writable, which is where APP_DIR and its
# work/ live. ReadWritePaths is therefore belt and braces, and it is here so
# that tightening ProtectSystem to `strict` later does not silently break
# every write the monitors do.
ReadWritePaths=%(app_dir)s

[Install]
WantedBy=multi-user.target
""" % {"app_dir": app_dir, "user": user, "python": python,
       "secrets": SECRETS_FILE}


def webhook_unit(app_dir=APP_DIR, user=APP_USER, python=HOST_PYTHON,
                 port=WEBHOOK_PORT):
    """The record-only receiver, as a unit.

    FOUND DURING THE SHADOW DEPLOY. The receiver was started by hand to prove
    it answered, and proving it answered is not the same as it being there
    tomorrow: with no unit it does not survive a reboot, and the first
    unattended 02:00 reboot would have left Caddy proxying to a closed port
    and every webhook answered with a 502 nobody was watching for.

    It is deliberately a SEPARATE unit from the supervisor. The receiver
    records and never acts; the supervisor runs the monitors. Coupling them
    would mean stopping the estate to restart the receiver, and starting the
    receiver whenever the estate starts - which is exactly what the shadow
    phase needs to not happen.
    """
    return """\
[Unit]
Description=Resonate record-only webhook receiver
Documentation=file://%(app_dir)s/docs/SERVER-PACKAGE-2B-SYSTEMD-UNITS.md
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=%(user)s
Group=%(user)s
WorkingDirectory=%(app_dir)s
# WEBHOOK_SIGNING_SECRET lives here. Without it the receiver refuses every
# POST rather than recording an unverified one, which is the right failure
# but a confusing one to debug if this line is missing.
EnvironmentFile=%(secrets)s
ExecStart=%(python)s %(app_dir)s/scripts/server/webhook_receiver.py \\
    --record-dir %(app_dir)s/work/webhooks --host 127.0.0.1 --port %(port)d
Environment=PYTHONUNBUFFERED=1

Restart=always
RestartSec=5
StartLimitIntervalSec=300
StartLimitBurst=10

NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ProtectHome=false
ProtectKernelTunables=true
ProtectControlGroups=true
RestrictSUIDSGID=true
ReadWritePaths=%(app_dir)s

[Install]
WantedBy=multi-user.target
""" % {"app_dir": app_dir, "user": user, "python": python,
       "secrets": SECRETS_FILE, "port": port}


def manifest(table, now=None):
    """What the estate will watch, as a record for the cutover.

    A RECORD, NOT AN INPUT. Nothing reads this back; the supervisor derives
    the table itself at runtime. It exists so a person can compare what the
    rule produces against what they expected BEFORE starting anything, which
    is the check that would have caught 496/497/498 being absent.
    """
    now = now or datetime.datetime.now(datetime.timezone.utc)
    lines = [
        "# Derived monitor table at %s" % now.replace(microsecond=0).isoformat(),
        "#",
        "# GENERATED. Not read by anything - the supervisor derives this",
        "# itself on every tick, which is why a campaign that goes live after",
        "# this file was written is still watched. Compare, do not edit.",
        "#",
        "# %-28s %-34s %s" % ("monitor", "heartbeat file", "why"),
        "",
    ]
    for mon in table:
        beat = supervisor.heartbeat_file(mon)
        lines.append("%-30s %-34s %s" % (
            mon["name"],
            os.path.basename(beat) if beat else "(none)",
            mon.get("derived", "static")))
    lines.append("")
    lines.append("# %d monitors" % len(table))
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Generate the estate's systemd units")
    ap.add_argument("--out-dir", help="write the unit and manifest here")
    ap.add_argument("--check", action="store_true",
                    help="read the table and print, write nothing")
    ap.add_argument("--app-dir", default=APP_DIR)
    ap.add_argument("--user", default=APP_USER)
    ap.add_argument("--python", default=HOST_PYTHON)
    args = ap.parse_args()

    try:
        table = supervisor.monitors()
    except supervisor.RegistryUnreadable as exc:
        sys.stderr.write(
            "REFUSING to generate a unit: %s\n\n"
            "A unit generated from an unreadable registry is a unit for an\n"
            "estate with no campaign watchers in it, and it would start,\n"
            "run, and report healthy.\n" % (exc,))
        return 2

    unit = supervisor_unit(args.app_dir, args.user, args.python)
    hook = webhook_unit(args.app_dir, args.user, args.python)
    man = manifest(table)

    if args.check or not args.out_dir:
        sys.stdout.write(unit)
        sys.stdout.write("\n")
        sys.stdout.write(hook)
        sys.stdout.write("\n")
        sys.stdout.write(man)
        sys.stdout.write("\n")
        sys.stderr.write("\n--check: nothing written. %d monitors.\n"
                         % len(table))
        return 0

    os.makedirs(args.out_dir, exist_ok=True)
    # newline="\n" EXPLICITLY. A unit file written from Windows with CRLF is
    # defect 4f wearing a different hat: `systemd` tolerates it in most
    # places and not all, and the failure names neither line endings nor the
    # machine the file came from.
    for name, text in ((SUPERVISOR_UNIT, unit),
                       (WEBHOOK_UNIT, hook),
                       ("MONITOR-TABLE.txt", man)):
        path = os.path.join(args.out_dir, name)
        with io.open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        sys.stderr.write("wrote %s\n" % path)
    sys.stderr.write("%d monitors in the manifest.\n" % len(table))
    return 0


if __name__ == "__main__":
    sys.exit(main())
