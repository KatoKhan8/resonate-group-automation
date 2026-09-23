# Cold start — the runbook, and the controlled reboot

**D1.** For the production session, tonight, in the no-send window.

The 2026-09-23 restart is the case this is written against. From
`docs/MACHINE-HARDENING-2026-09-23.md`: Windows Update restarted the machine
at **05:29** and it was back at **05:32** — three minutes. The monitors were
down until somebody noticed, **four hours later**. That document's own closing
line is the brief for this one:

> *"Does not, and is the bigger gap: bring the monitors back. Every control in
> this document is about preventing a restart; none of them survives one."*

---

## 1. WHAT IS NEW, AND THE ONE THING TO UNDERSTAND BEFORE RUNNING IT

    scripts/cold_start.py         plan, start, verify
    scripts/install_autostart.py  register it at logon
    tests/test_the_estate_comes_back_after_a_reboot.py   22 tests

**A monitor is UP only with TWO WITNESSES**, and this is the substance of the
change rather than a flourish:

    witness 1   a live process, from the supervisor's state file, AND that
                state file written AFTER the current boot
    witness 2   a heartbeat written AFTER the current boot, and no older
                than twice that monitor's own poll interval

**Neither is admissible alone, because the one we already had is forgeable.**
`supervisor._monitor_status` decides a monitor is UP by asking whether the pid
in its state file is alive. **Pids are reused across a reboot.** After a
restart the number in a pre-boot state file names whatever process the kernel
handed it to next, so `--status` can report UP for a monitor that is not
running.

That matters directly to last night's plan. `PRODUCTION-HANDOFF-2026-09-23-OVERNIGHT.md`
§ item 2 makes the adoption proof *"post `--status` showing all UP"* — which is
exactly the claim a reused pid forges. Use `cold_start` for that check
tonight, not `supervise --status`.

The second witness is not redundant either: a monitor that is alive but wedged
keeps its pid and beats nothing, and a beat from before the reboot is a record
of the machine's previous life.

---

## 2. TONIGHT, IN ORDER

Everything up to step 4 is read-only. **Nothing here sends.**

### Step 1 — look before touching (safe any time, including now)

    py -3 -m scripts.cold_start

Prints every monitor with both witnesses, every lock sorted into stale and
live, and every watcher's last beat. Starts nothing, removes nothing.

### Step 2 — register the autostart

    py -3 -m scripts.install_autostart              # shows the exact command
    py -3 -m scripts.install_autostart --install
    py -3 -m scripts.install_autostart --status

One Scheduled Task, at logon, as the current user. **No elevation** — that is
deliberate, because §7 of the hardening doc is still waiting on an elevated
shell and this must not join that queue.

### Step 2b — the keep-awake request, now that it has a caller

`src/keepawake.py` landed on master with **no caller**: hardening §6 says
*"Where it is wired: nowhere yet, on purpose"*, because the supervisor lives
on `infra` and the production session does not edit another session's
in-flight files. That one line is now written, on the side of the rule that
owns the file — `supervisor._run` holds the request around the whole loop and
releases it on every exit, including a crash.

So **`powercfg /requests` will only name a process once the supervisor is
running** (step 3). Checking it before that names nothing, correctly.

**And `powercfg /requests` itself requires elevation** — hardening §6 records
that it could not be run for exactly this reason, and §7 is still waiting on
an elevated shell. In a normal shell it prints an access-denied error, not an
empty list, and the two look nothing alike: if you get an empty list you have
a real finding, if you get an error you have the known one.

If the request is refused, the supervisor says so on stdout
(`SUPERVISOR KEEP-AWAKE REFUSED …`) and **keeps supervising**. That line is
the cheaper check, and it needs no elevation.

### Step 3 — start the supervisor under the cold start

    py -3 -m scripts.cold_start --start

It clears the locks that provably predate the boot, **refuses if a supervisor
is already up**, and hands over to `src/supervisor.py`, which owns starting
and restarting. It is a foreground process; leave it running.

Adopt monitors the way the overnight handoff says — one at a time, least
critical first, never two instances of one. The refusal in step 3 is the
mechanical half of that rule.

### Step 4 — the controlled reboot, after 23:00 Zagreb

Confirm no campaign is sending first. Then reboot, log back in, and:

    py -3 -m scripts.cold_start --verify

It polls until every monitor has **both** witnesses and prints the recovery
time **measured from the boot**, not from when you typed it — so the number is
the one that matters: how long the estate was actually down.

Target: under ten minutes. `--verify` gives up at ten and names what is still
missing, because a supervisor that has not brought eight monitors up in ten
minutes is not slow, it is stuck.

---

## 3. THE LIMITATION, STATED BEFORE IT IS DISCOVERED IN AN INCIDENT

**At logon, not at boot.** An at-boot task runs as SYSTEM, in a different
profile, without the user's environment — and `config/.env` lives in the
user's checkout. So an unattended restart recovers **when somebody logs in**.

With Windows set to restart and sign back in automatically, that is the same
moment. Without it, it is not, and the four-hour gap can happen again with
every control in this document working perfectly.

**That setting is the other half of this change and it is not made here.** It
belongs with hardening §7, which already needs an elevated shell. Until then
this closes the gap for an attended restart and narrows it for an unattended
one; it does not close it.

---

## 4. WHAT IT DOES NOT TOUCH

No sends. No queue record written. Nothing under `config/.env`,
`src/providers/*` or `work/` is modified — `work/` is read for cursors and
heartbeats, and the only files removed anywhere are lock files whose mtime
**provably predates the current boot**.

**It fails closed.** If the boot time cannot be read, no lock is cleared and
no monitor is reported UP — both witnesses are dated against the boot, and
clearing a live monitor's lock is worse than leaving a dead one's.

---

## 5. ROLLBACK

    py -3 -m scripts.install_autostart --uninstall

Then stop the supervisor with Ctrl-C. Nothing else changes: the scripts are
additive, no existing monitor or loop was modified, and `supervise --status`
still works exactly as it did.

---

## 6. FOR INCREMENT F

`install_autostart.py --install` prints the equivalent **systemd unit**,
generated from the same `command()` the Scheduled Task registers, so the
server migration writes its unit from a command known to work rather than
from a second reading of this document. A test asserts the two agree.

Both use `sys.executable`, never `py -3` — that launcher does not exist on
Linux, which is the same reason `src/supervisor.py` resolves its children the
same way.

---

## 7. WHAT THE TESTS PROVE

22 tests, mutation-checked twice. Weakening the rule from "both
witnesses" to "either witness" turns four of them red; removing the power
request from the supervisor turns two more red.

    a live pid from a PRE-BOOT state file          -> not UP  (the forged UP)
    a live process with no fresh beat              -> not UP  (wedged)
    a fresh beat with no live process              -> not UP  (started, died)
    a beat from before the boot                    -> not a witness
    an unreadable boot time                        -> confirms nothing
    a lock older than the boot                     -> stale
    no boot time                                   -> nothing is stale
    a supervisor already up                        -> --start refuses, and the
                                                      refusal happens before
                                                      `supervisor._run` is
                                                      reached at all
