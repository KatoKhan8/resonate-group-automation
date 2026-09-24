# 2b — the systemd units, generated from the monitor table

Branch `infra`. Built 2026-09-24 on the settled one-table decision.
`scripts/server/generate_units.py` is the generator;
`tests/test_the_units_come_from_the_table.py` is what holds it.

**Status: BUILT and TESTED, NOT INSTALLED.** Nothing has been copied to the
host and nothing has been started. Installation is item 3, the shadow
deploy, and it deliberately leaves the monitors stopped.

---

## 1. ONE UNIT RUNS THE ESTATE

The obvious reading of "units generated from the monitor table" is one unit
per monitor — `bison-497.service`, and so on. **It is the wrong shape here,
and the reason is the same one that made `MONITORS` a function.**

`supervisor.monitors()` is derived. A table computed once freezes, and
`test_the_table_is_not_frozen_at_import` pins that. **Units written to disk
at deploy time freeze it harder**: a campaign that goes live at noon would
have no unit until somebody regenerated and ran `daemon-reload`. That is the
hand-written list again, wearing systemd's clothes — a campaign that can send
with nothing watching it, discovered by a person noticing. Campaign 497 is
what that costs.

`src/supervisor.py` is already built to be the thing systemd runs: foreground,
logs to stdout/stderr, SIGTERM stops children cleanly, no daemonising, no
pidfile. It already owns per-monitor locking (`singlewalker`), restart with
backoff (30s, doubling, 10-minute ceiling), heartbeat reading and
notification. **Per-monitor units would put a second restart policy beside
that one, and two restart policies for one process is how a monitor comes to
be running twice.**

So:

    resonate-supervisor.service   ->  python3 -m scripts.supervise

and the supervisor derives the table on every tick. A campaign launched at
noon is watched at noon, with nothing regenerated and nothing deployed.

`test_no_per_monitor_units_are_written` fails if somebody reverses this, and
points at the reason rather than at a style preference.

---

## 2. WHAT IS THEN "GENERATED FROM THE TABLE"

The **unit** is generated — interpreter, paths, user, environment file — and
the **table is read, validated, and written beside it** as
`MONITOR-TABLE.txt`.

That manifest is **a record, never an input.** Nothing reads it back. It
exists so a person can compare what the rule produces against what they
expected *before starting anything* — which is exactly the check that would
have caught 496, 497 and 498 being absent.

It names each monitor's **actual heartbeat file**, asked of
`supervisor.heartbeat_file()` rather than guessed from the monitor's name.
A manifest that guessed `<name>.json` would show files nothing writes, which
is the `46474c6c` defect reappearing in the artifact a person reads at
cutover.

---

## 3. THE GENERATOR REFUSES RATHER THAN WATCHING NOTHING

`campaigns.load()` answers an absent registry with an empty snapshot. A
generator that shrugged at that would emit a **perfectly valid unit for an
estate with no campaign watchers in it**, start it, and report healthy.

`supervisor.monitors()` raises `RegistryUnreadable` for that case and this
script exits **2**, writing nothing. The refusal says what it prevented,
because a refusal that does not is one the next person in a hurry overrides.

    $ py -3 scripts/server/generate_units.py --check
    REFUSING to generate a unit: campaign registry not found at ...
    A unit generated from an unreadable registry is a unit for an
    estate with no campaign watchers in it, and it would start,
    run, and report healthy.
    $ echo $?
    2

---

## 4. THE UNIT, AND THE LINES THAT ARE NOT OBVIOUS

    ExecStart=/usr/bin/python3 -m scripts.supervise

**The interpreter is the HOST's, never `sys.executable`.** This is authored
on Windows. A unit carrying `C:\...` generates cleanly, commits cleanly, and
dies at `systemctl start` naming a path nobody on the host recognises —
defect 4f's shape exactly, where the symptom names neither the machine the
file came from nor the line. `test_no_windows_path_reaches_the_unit` asserts
on the bytes, and so does the CRLF check: `.gitattributes` pins `*.service`
to LF because the working tree is what reaches the host, and a Python
`write_text` on Windows re-introduces CRLF by default.

    KillSignal=SIGTERM
    TimeoutStopSec=90

SIGTERM is what the supervisor handles. **A SIGKILLed supervisor leaves
orphaned monitors holding their locks**, and the next start finds every lock
taken and watches nothing.

    Restart=always
    StartLimitIntervalSec=300
    StartLimitBurst=10

**Neither the default nor unlimited.** The default gives up after 5 starts in
10 seconds and leaves the unit `failed` — an estate that is down and looks
configured. `0` disables the limit and crash-loops a genuinely broken deploy
forever. This is wide enough that a transient fault always recovers and
narrow enough that a broken one lands in `failed`, where `systemctl status`
and `cold_start --verify` both say so.

    EnvironmentFile=/etc/resonate/secrets.env

640 `root:resonate`, created empty by provisioning and filled by 2d. systemd
reads it **as root, before dropping to `resonate`**, which is why it does not
need to be readable by the app user's shell.

    ProtectSystem=full
    ReadWritePaths=/home/resonate/resonate-group-automation

`work/` is written by every monitor. `ProtectSystem=full` leaves `/home`
writable, so `ReadWritePaths` is belt and braces — it is there so that
tightening to `strict` later does not silently break every write.

---

## 5. VERIFICATION

    tests/test_the_units_come_from_the_table.py     13 green

**Five mutations, five killed:**

    HOST_PYTHON = sys.executable (Windows path leaks)   FAILED
    unit written with the default newline (CRLF)        FAILED
    registry refusal swallowed, empty table             FAILED (2)
    manifest guesses <name>.json for the heartbeat      FAILED
    per-monitor units emitted as well                   FAILED

Two of those five first reported OK against a mutation that had **not
actually been applied** — a shell heredoc was collapsing the `\n` escape, so
the patch silently no-op'd. Both were re-run with the escape built via
`chr(92)` and both then killed the tests. A mutation that does not change the
file is a green that means nothing, and it looks identical to a passing one.

---

## 6. WHAT IS STILL NEEDED BEFORE THIS RUNS

    2c   deploy.sh          puts the repository on the host at a tag
    2d   secrets checklist  fills /etc/resonate/secrets.env
    item 3  shadow deploy   installs the unit, does NOT start it

The unit is installed to `/etc/systemd/system/` by `deploy.sh`, not by this
generator. The generator writes to a directory you name and touches nothing
outside it.
