PRIORITY: P1
DEPENDS:

# TASK-263 — one supervisor for every monitor, replacing nohup

**The operator calls this "the recurring failure class" and the evidence is in
the repository's own history.** Monitors are launched with bare `nohup`, which
means: nothing stops two of the same monitor running, nothing restarts a
crashed one, nothing notices when one dies, and a watcher that is not running
is indistinguishable from one reporting no activity.

CLAUDE.md's own handoff records `bison_watch_loop` surviving a breaking change
"only because it predates the guard by 3h and holds the old module in memory;
**any restart would have killed the only LinkedIn monitor**". That is the
shape of the problem: nobody knew, because nothing watched the watchers.

## Build

`src/supervisor.py` plus `scripts/supervise.py`.

### What it declares

A table of monitors, by name, in ONE place — the thing that does not exist
today. From the 2026-09-22 handoff:

    name                      module/args                              interval
    bison_mailbox_utilisation scripts.bison_mailbox_utilisation        300
    reply_watch               scripts.reply_watch_loop                 300
    notify_deliver            scripts.notify_deliver_loop               60
    bison_watch_487           scripts.bison_watch_loop --campaign 487  180
    bison_watch_489           scripts.bison_watch_loop --campaign 489  180
    heyreach_watch            scripts.heyreach_watch_loop              300
    digest                    scripts.digest_loop                      300
    slack_agent               scripts.slack_agent_loop                  -

**Re-derive this from the current handoff before you hardcode it**, and make
the table data rather than code so a monitor can be added without editing the
supervisor.

### What it must do

1. **One lock per monitor, so a duplicate cannot start.** `src/singlewalker.py`
   already implements exactly this — `acquire(path)` raises `AlreadyWalking`,
   `_alive(pid)` checks liveness, `release(path)`. **Use it. Do not write a
   second lock.** A second implementation of a lock is how the two disagree.
2. **Restart a crashed monitor with backoff.** Start at 30 seconds, double to
   a ceiling of 10 minutes, reset on a clean run of some duration. **Not 1
   second** — a provider returning 429 answered by an instant restart is a
   self-inflicted rate limit.
3. **Resolve the interpreter ONCE**, as `sys.executable`. Not `py -3`, not
   `python`, not a PATH lookup. `py -3` does not exist on Linux and this has
   to survive the server migration unchanged.
4. **Record pid, heartbeat and exit code per monitor.** `src/watchsink.py`
   already has `heartbeat_dir()`, `heartbeat_path(source, campaign)` and
   `events_path(...)`. **Use them.** The supervisor adds pid and exit code; it
   does not invent a parallel heartbeat file.
5. **Post to `#resonate-notifications` when a monitor dies twice in an hour.**
   Through `src/notify.py` and the existing routing table — NOT a direct Slack
   call. SLACK-NOTIFICATIONS.md is the standing contract for that layer: two
   levels, no fallback between them.
6. **Run under systemd later without change.** That means: foreground
   process, logs to stdout/stderr, SIGTERM stops children cleanly, no
   daemonising, no pidfile of its own. `docs/SERVER-MIGRATION-PLAN.md` §2 has
   the unit template it must fit.

### `--status`

Prints every declared monitor: running or not, pid, last heartbeat age, last
exit code, restart count this hour. **A monitor declared and not running must
be visibly DOWN rather than absent from the output** — that is the whole
point, and an absent row reads as "fine" to a tired reader at 2am.

## Falsifiable requirements

1. Two supervisors, or a supervisor plus a hand-started monitor of the same
   name, cannot both run it. The second refuses with `AlreadyWalking`.
   **Test it with two real processes**, not by calling `acquire` twice in one.
2. A monitor that exits non-zero is restarted; the interval doubles; it caps.
   Drive it with a fixture monitor that exits on command rather than by
   waiting.
3. A monitor that dies twice in an hour produces exactly ONE notification —
   not one per death, and not one per supervisor tick.
4. `--status` shows a declared-but-not-running monitor as DOWN.
5. SIGTERM to the supervisor stops every child. No orphans. Assert by pid.
6. The interpreter used is `sys.executable`, asserted by reading the spawned
   command, not by grepping the source.
7. It writes nothing under `work/` in a test — `store.refuse_production_write`.

## Do not

- Do not start, stop or restart any monitor against production in this task.
  **Build it and test it with fixture monitors.** Adoption is a merge request
  and belongs to the production session.
- Do not write a second lock, a second heartbeat format, or a second Slack
  path.
- Do not use `timeout`. Ever. The supervisor IS the supervision.
- Do not edit `config/.env`, `src/providers/*`, `scripts/*_watch_loop.py` or
  anything under `work/`. **The loops themselves are not yours** — the
  supervisor runs them unmodified.
