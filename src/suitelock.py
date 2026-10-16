"""One full test suite at a time, machine-wide.

WHY THIS EXISTS, MEASURED 2026-10-02. Six `tests.offline` workers ran at once from
four separate launches. The full suite takes 2100-2720s alone; six in parallel made
every one of them look stalled, and the operator spent 3h42 waiting on a merge
verdict that was only contending. `CLAUDE.md` already warned that `unittest
discover` and `tests.offline` both bind loopback and build demo estates, and that
two runs back to back still overlap during teardown. Six at once is worse than slow:
the results are not trustworthy, because a port collision and a half-torn-down demo
estate are indistinguishable from a real failure.

WHY THE LOCK IS NOT IN THIS WORKTREE'S `work/`. Measured the same day: `work/` is
gitignored, so every worktree has its OWN, and `store.PRODUCTION_WORK` resolves
relative to each worktree's own ROOT - from a worktree it points at that worktree's
`work/`. A lock there would have serialised nothing, because the six runs came from
six different trees. `git rev-parse --git-common-dir` is the one path that resolves
identically from the main checkout and from every worktree, so the lock lives beside
the MAIN checkout's `work/`.

A STALE LOCK IS TAKEN OVER, LOUDLY. A machine that lost power mid-suite must not
need a human to delete a file before tests can run again. So a lock whose PID is no
longer alive is reported and replaced. A lock whose PID IS alive is waited on - never
stolen, and never ignored.

WHAT THE FIRST PRODUCTION USE FOUND, AND THIS FILE NOW FIXES. On 2026-10-02 four
runs queued behind one holder and two defects showed immediately:

* grants were unordered - whoever polled first after a release won, so arrival
  order bought a waiter nothing and a run could be overtaken until it timed out.
  There is a ticket queue now, below.
* the `branch` field read `"HEAD"`, because every reference and gate checkout is
  DETACHED on purpose. The one field that tells a waiting run who is ahead of it
  named nothing, and three agents went looking for the holder by hand. `_label`
  resolves a detached checkout to its commit.
"""
import json
import os
import subprocess
import time

#: How long a waiting run will sit before giving up.
#:
#: MEASURED 2026-10-02, after the old 4200s starved the one run that mattered.
#: Six full suites finished that day in 2281.5, 2353.9, 2453.3, 2608.3, 2718.6
#: and 2767.0 seconds. So 4200s - 70 minutes - cannot survive even TWO runs
#: ahead of you, and the frozen master reference, launched with the default while
#: every track had asked for 10800 or more, was overtaken twice and raised
#: `SuiteBusy` after 70 minutes without running a single test. The reference that
#: every other branch had to be diffed against was the one thing the queue threw
#: away.
#:
#: 21600s is six hours: enough for six suites ahead of you at the measured pace.
#: Waiting that long is not an error state - a dead holder is taken over in
#: seconds by `_alive`, so the only way to wait this long is a live queue, and
#: the only alternative to waiting is two suites at once, which is the thing this
#: module exists to prevent.
DEFAULT_TIMEOUT = 21600.0

#: WHY THERE IS A TICKET QUEUE AND NOT JUST AN `O_EXCL` RACE. Measured on this
#: lock's FIRST production use, 2026-10-02: four runs waited behind one holder and
#: `acquire` granted the lock to whichever of them happened to poll first after the
#: release. Launch order and grant order are unrelated under that rule, so a waiter
#: can be overtaken repeatedly and time out while later arrivals run - with a 46
#: minute suite and a 3 hour `--lock-wait`, four overtakes is enough to starve one.
#:
#: A TICKET MUST NEVER BE ABLE TO BLOCK A RUN. If the queue directory cannot be
#: created, listed or written, `acquire` falls back to exactly the race it had
#: before and says so out loud. That is worse fairness and the SAME serialisation,
#: which is the property the operator's rule is actually about.
QUEUE_SUFFIX = ".queue"

#: How long a lock whose CONTENT cannot be read is treated as ALIVE rather than
#: stale. The atomic publish above should make an empty lock unreachable; this
#: covers the fallback path, where the file exists for a moment before its bytes
#: do. 30s is far longer than that moment and far shorter than a suite, so a
#: genuinely damaged lock is still recoverable without a human.
DAMAGED_GRACE = 30.0

#: How often the waiter looks. Cheap: it is one `os.path.exists` and a read.
POLL = 5.0

#: The three answers `_pid_identity` may give. A BOOL cannot carry the middle
#: one, and the middle one is the whole point: "this PID is in use by something
#: whose identity I cannot read" is not the same claim as "the holder is alive",
#: and collapsing them is how a lock gets stolen or a machine gets wedged.
ALIVE = "ALIVE"
DEAD = "DEAD"
UNKNOWN = "UNKNOWN"

#: The answers `holder_state` may give, which are about the LOCK rather than
#: about a process. UNKNOWN is shared with the list above: an unreadable holder
#: is an unknown lock state.
HELD = "HELD"
STALE = "STALE"

#: `OpenProcess` last-error values that prove the PID is in use by NOTHING.
#: MEASURED 2026-10-16: a pid that has never existed (999997) fails with 87,
#: `ERROR_INVALID_PARAMETER`. Every OTHER failure - 5, `ERROR_ACCESS_DENIED`,
#: measured against `csrss.exe` and `wininit.exe` - means a process with that
#: number EXISTS and this reader may not look at it. That is UNKNOWN, and
#: UNKNOWN waits. Treating an access failure as death is how a live holder
#: loses its lock.
PID_ABSENT_ERRORS = frozenset((87,))

#: Least privilege that answers `GetProcessTimes`. Asking for
#: `PROCESS_QUERY_INFORMATION` instead would turn readable same-user processes
#: into ACCESS_DENIED for no gain.
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

#: Seconds between 1601-01-01 and 1970-01-01, to turn a Windows FILETIME into
#: an epoch float. Only used for the ordering check below, never for display.
FILETIME_EPOCH_DELTA = 11644473600

#: How much later than its own lock file a holder may appear to have been
#: created before that is read as a RECYCLED pid.
#:
#: WHY THERE IS A SECOND, WEAKER CHECK AT ALL. The strong check compares the
#: creation stamp the holder RECORDED against the one its pid reports now, and
#: it is exact - but it only works for locks written by this version. The lock
#: sitting on this machine at 2026-10-16T16:39 carries no such field, and nor
#: does any lock written before this change lands. The ordering check retrofits
#: onto those: a process cannot have published a lock file before it existed,
#: so a creation time LATER than the lock file mtime PROVES the pid is not the
#: holder, whatever the lock records.
#:
#: Both numbers are absolute - a FILETIME and an `st_mtime` - so this comparison
#: is deliberately NOT made against the lock's `queued_at` string, which is
#: naive local time at second resolution. Parsing that with `mktime` across a
#: DST transition can be an hour out in either direction, and an hour out in the
#: wrong direction reads a LIVE holder as recycled, which is fail-OPEN.
#:
#: MEASURED against the real holder on 2026-10-16: pid 99260 was created
#: 1792161583.055857 and its lock file mtime is 1792161583.640058, so
#: `created - mtime` is -0.584201s. A true holder is NEGATIVE here, by the time
#: it takes to import and acquire.
#:
#: WHY 60s AND NOT THE 0.6s THAT GAP SUGGESTS. The two errors are not
#: symmetrical and the slack is sized against the worse one.
#:
#: Too SMALL, and a true holder is misread as recycled, its lock is DELETED, and
#: two suites run at once - the catastrophe this whole module exists to prevent,
#: and the one that destroyed 91 of 227 names. Reaching it needs the system
#: clock to step BACKWARDS between a holder being created and that holder
#: writing its lock, which is rare but is exactly what an NTP correction does.
#:
#: Too LARGE, and a pid recycled within the slack window is not caught BY THIS
#: CHECK - and that costs almost nothing, because this check is only ever the
#: fallback. Any lock written by this version carries `pid_started`, and the
#: exact comparison against it has no tolerance at all. The window also has to
#: be crossed by a real recycle, and the one on this machine reissued a number
#: roughly 80 minutes after the lock was written.
#:
#: So: generous. 60s absorbs any plausible clock step and is still three orders
#: of magnitude below the gap a real recycle leaves.
CLOCK_SLACK = 60.0


class SuiteBusy(RuntimeError):
    """Another suite holds the lock and did not finish inside the timeout.

    Carries the holder's details so the message names who to look at rather than
    telling the reader to go hunting.
    """


def _git_common_dir():
    """The main checkout's `.git`, from the main checkout or any worktree, or None.

    `--path-format=absolute` matters: without it git answers a RELATIVE path from a
    worktree, which would resolve against the caller's cwd and defeat the purpose.
    """
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
            capture_output=True, text=True, timeout=20, check=False)
    except Exception:                                          # noqa: BLE001
        return None
    if out.returncode != 0:
        return None
    value = (out.stdout or "").strip()
    if not value:
        return None
    # A RELATIVE answer is refused rather than resolved. `os.path.abspath` would
    # resolve it against the caller's cwd, which from a worktree is that
    # worktree - the per-tree lock this module exists to prevent. The flag above
    # should make this unreachable; this is the check that does not trust it.
    if not os.path.isabs(value):
        return None
    return value


def path():
    """Where the one lock lives. The main checkout's `work/suite.lock`.

    Falls back to this tree's own `work/` when git cannot answer, and the lock
    records that it did, because a lock that silently became per-worktree is the
    exact defect this module was written for.
    """
    common = _git_common_dir()
    if common:
        return os.path.join(os.path.dirname(os.path.abspath(common)),
                            "work", "suite.lock")
    from src import store
    return os.path.join(store.PRODUCTION_WORK, "suite.lock")


def _alive_tasklist(pid):
    """The old liveness reader, kept as the fallback when `ctypes` cannot answer.

    MEASURED 2026-10-02, because it decides whether this whole module is sound:
    `tasklist` invoked through `subprocess`, as here, DOES answer correctly - a
    known-live pid comes back in the table and a nonexistent one produces the
    "No tasks are running" line. The same command typed into a Git Bash shell
    returns nothing at all for every query, which is how a live holder was briefly
    reported dead by a human reader. The reader here is not that one.

    It cannot distinguish "not running" from "cannot be read", so it answers
    True for both. That is safe for liveness and useless for identity, which is
    exactly why `_pid_identity` exists above it.
    """
    try:
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                             capture_output=True, text=True, timeout=20,
                             check=False)
    except Exception:                                          # noqa: BLE001
        return True
    return str(pid) in (out.stdout or "")


def _pid_identity_windows(pid):
    """`(state, token)` on Windows, from `OpenProcess` + `GetProcessTimes`."""
    try:
        import ctypes
        import ctypes.wintypes as wintypes
    except Exception:                                          # noqa: BLE001
        return (ALIVE if _alive_tasklist(pid) else DEAD), None

    class _FileTime(ctypes.Structure):
        _fields_ = [("low", wintypes.DWORD), ("high", wintypes.DWORD)]

    try:
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.OpenProcess.restype = wintypes.HANDLE
        k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL,
                                    wintypes.DWORD]
        k32.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            code = ctypes.get_last_error()
            if code in PID_ABSENT_ERRORS:
                return DEAD, None
            # ACCESS_DENIED, and anything else unrecognised: a process with this
            # number exists and cannot be inspected. Not dead, not identified.
            return UNKNOWN, None
        try:
            created = _FileTime()
            exited = _FileTime()
            kernel = _FileTime()
            user = _FileTime()
            ok = k32.GetProcessTimes(handle, ctypes.byref(created),
                                     ctypes.byref(exited),
                                     ctypes.byref(kernel), ctypes.byref(user))
            if not ok:
                return UNKNOWN, None
            exit_ft = (exited.high << 32) | exited.low
            create_ft = (created.high << 32) | created.low
            # THE TRAP, and the reason this function returns a state rather than
            # a bool. MEASURED 2026-10-16: pid 67800 was spawned, reaped, and
            # then `OpenProcess` STILL succeeded for it and STILL reported a
            # creation time - created 14:44:16.186564Z, exited 14:44:16.214101Z,
            # 28 milliseconds later - because a handle to it was still open. A
            # reader that took openability for liveness would call that corpse
            # the holder for as long as the handle lived. The exit time is the
            # thing that answers, and a non-zero one means EXITED.
            if exit_ft:
                return DEAD, None
            if not create_ft:
                return UNKNOWN, None
            return ALIVE, "ft:%d" % create_ft
        finally:
            k32.CloseHandle(handle)
    except Exception:                                          # noqa: BLE001
        return (ALIVE if _alive_tasklist(pid) else DEAD), None


def _pid_identity_posix(pid):
    """`(state, token)` on POSIX, from `/proc/<pid>/stat` field 22.

    NOT MEASURED on this machine, which is Windows 11 - and said rather than
    implied. Where `/proc` is absent (macOS) this degrades to `os.kill(pid, 0)`
    and returns no token, which makes the holder record `identity: "pid-only"`
    and makes the reader fall back to exactly the behaviour this file had before.
    A weaker answer stated beats a stronger one assumed.
    """
    try:
        with open("/proc/%d/stat" % pid, "rb") as handle:
            raw = handle.read()
    except FileNotFoundError:
        return DEAD, None
    except Exception:                                          # noqa: BLE001
        raw = None
    if raw:
        # `comm` is parenthesised and may itself contain spaces and brackets, so
        # the fields are counted from the LAST close bracket. `state` is then
        # field 3 at offset 0 and `starttime` is field 22 at offset 19.
        fields = raw.rpartition(b")")[2].split()
        try:
            if fields[0] == b"Z":
                return DEAD, None
            return ALIVE, "jiffies:%d" % int(fields[19])
        except (IndexError, ValueError):
            pass
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return DEAD, None
    except PermissionError:
        return UNKNOWN, None
    except Exception:                                          # noqa: BLE001
        return UNKNOWN, None
    return ALIVE, None


def _pid_identity(pid):
    """`(state, token)` for a PID: ALIVE with its creation stamp, DEAD, or UNKNOWN.

    WHY THIS EXISTS. MEASURED 2026-10-16, in this lane's own precondition check
    for TASK-0396: the machine-wide lock had been held for 89 minutes by a run
    that died at process start - exit code 3221225794, which is `0xC0000409`, a
    stack buffer overrun; `wall_seconds=0.0`; a 0-byte log - and the same pid,
    79548, answered DEAD and then ALIVE four minutes apart, because Windows had
    recycled that number onto a transient process of the reader's own shell.
    `_alive` was correct about the PID both times. The PID was not the holder.

    That is a fail-OPEN defect wearing a fail-closed coat. `_takeable` asked
    `_alive(pid)` and returned False - lock held, keep waiting - the moment the
    OS handed that number to anything at all. The suite is the merge gate's only
    instrument, so a ghost lock whose number gets recycled blocks every lane on
    this machine at once, for as long as the recycled process happens to live.

    A PID is a slot, not a name. The name is the pid paired with the process
    CREATION TIME: absolute, never reused, and not choosable by the process
    itself, so it cannot be forged by anything that is not already the kernel.

    VERIFIED ON THIS MACHINE rather than asserted, which matters because "start
    time pairs with the pid" is a claim that is usually repeated. All four
    branches below were reached deliberately on 2026-10-16:

      this process                 OK,  created 2026-10-16T14:44:15.140948Z
      pid 99260, ANOTHER session   OK,  created 2026-10-16T14:39:43.055856Z
      csrss.exe, wininit.exe       OpenProcess fails 5, ACCESS_DENIED -> UNKNOWN
      pid 999997, never existed    OpenProcess fails 87 -> DEAD

    The second line is the one the fix rests on: the creation time of a process
    this reader does NOT own is obtainable, to the microsecond. 99260 was the
    live suite holding the real lock at the time, and its stamp matched that
    lock's own `started_at` of 16:39:43 to the second.
    """
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return DEAD, None
    if pid <= 0:
        return DEAD, None
    if os.name == "nt":
        return _pid_identity_windows(pid)
    return _pid_identity_posix(pid)


def _alive(pid):
    """Is this PID running? Unknown counts as ALIVE, so a lock is never stolen
    on a guess - waiting costs time, stealing costs a corrupted run.

    Kept with its original contract because a QUEUE TICKET carries only a pid in
    its name and has no stamp to compare against, so ordering can only ever ask
    the weak question. The LOCK asks `holder_state` instead, which is the one
    place this distinction decides whether a file is deleted.
    """
    return _pid_identity(pid)[0] != DEAD


def read(file_path=None):
    """The current holder as a dict, or None. Never raises on a damaged file -
    an unreadable lock is reported as a holder with no pid, which is then treated
    as stale rather than blocking every suite on this machine forever."""
    file_path = file_path or path()
    try:
        with open(file_path, encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        return None
    except Exception:                                          # noqa: BLE001
        return {"pid": None, "damaged": True, "lock_path": file_path}


def _write_in_place(file_path, blob):
    """The old one-step publish. Still the mutex, but briefly empty - which is
    why `DAMAGED_GRACE` exists. Only reached when staging or linking is
    impossible on this filesystem."""
    handle = os.open(file_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        os.write(handle, blob)
    finally:
        os.close(handle)


def _write(file_path, payload):
    """Publish the lock ATOMICALLY: it never exists with partial content.

    MEASURED 2026-10-02, and it was my own first version that caused it.
    `os.open(O_CREAT|O_EXCL)` followed by a SEPARATE `os.write` leaves the lock
    file momentarily EMPTY. `read()` deliberately turns an unreadable lock into
    `{"pid": None, "damaged": True}`, `_alive(None)` is False, and `acquire` then
    unlinks it as stale - so a LIVE holder's lock is stolen inside that window.
    It happened rather than being hypothesised: a holder's payload (pid 117216,
    13:19:00Z) was found replaced by another branch's while that pid was still
    running, and two suites then ran at once, which is the single thing this
    module exists to prevent.

    The fix is the classic one. The payload is staged in a private temp file and
    then HARD-LINKED into place. `os.link` raises `FileExistsError` when the
    target exists, so it is still the mutex, and the instant the lock file exists
    it already holds complete content. Verified on this machine: a second
    `os.link` to the same target does raise `FileExistsError`.
    """
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    blob = json.dumps(payload, sort_keys=True).encode("utf-8")
    tmp = "%s.%d.%d.tmp" % (file_path, os.getpid(), time.time_ns())
    try:
        handle = os.open(tmp, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        try:
            os.write(handle, blob)
        finally:
            os.close(handle)
    except Exception:                                          # noqa: BLE001
        return _write_in_place(file_path, blob)
    try:
        os.link(tmp, file_path)
    except FileExistsError:
        raise
    except Exception:                                          # noqa: BLE001
        return _write_in_place(file_path, blob)
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def _created_after_the_lock(file_path, token):
    """Was the process holding this pid created AFTER the lock file was written?

    If so it cannot be the holder, whatever the lock says, because a process
    cannot publish a file before it exists. This is the check that retrofits the
    recycle test onto a lock carrying no recorded stamp - every lock written
    before this change, including the one on this machine at 16:39 on 2026-10-16.

    Answers False on any doubt. An unparseable token, an unreadable mtime and a
    non-Windows token shape all mean "no conclusion", and no conclusion must
    never become a takeover: this function's False is read as "do not steal".
    """
    if not token or not token.startswith("ft:"):
        return False
    try:
        created = int(token[3:]) / 1e7 - FILETIME_EPOCH_DELTA
    except ValueError:
        return False
    try:
        written = os.path.getmtime(file_path)
    except OSError:
        return False
    return created > written + CLOCK_SLACK


def holder_state(file_path, holder):
    """`(state, reason)` for this lock: HELD, STALE or UNKNOWN, and why.

    The reason is returned rather than logged because all three operator-facing
    messages print it, and "stale" with no cause is what made the 89-minute ghost
    of 2026-10-16 look like a judgement call.

    ORDERED, AND THE ORDER IS THE SAFETY PROPERTY:

    * An unreadable lock is HELD until it has been unreadable for
      `DAMAGED_GRACE`. The fallback write path leaves the file empty for a
      moment and stealing inside that window takes the lock from a running
      suite - measured 2026-10-02.
    * A pid that nothing holds is STALE. A machine that lost power mid-suite
      must not need a human to delete a file.
    * A pid whose identity cannot be READ is UNKNOWN, and UNKNOWN WAITS. This is
      the branch that must never be allowed to collapse into either neighbour.
      Fail-open here means two suites writing one evidence path, which is how 91
      of 227 test names were destroyed with neither writer learning.
    * A pid that is alive but is NOT the process that took the lock is STALE,
      named `pid-recycled`. Two independent proofs, either of which suffices:
      the recorded creation stamp disagrees with the current one, or the current
      process was created after the lock file was written.
    * Only then HELD.
    """
    if not holder:
        return STALE, "no-lock"
    if holder.get("damaged"):
        try:
            age = time.time() - os.path.getmtime(file_path)
        except OSError:
            # Unreadable content AND an unreadable mtime: there is nothing left
            # to wait on, and the grace cannot be evaluated at all.
            return STALE, "damaged-and-unstattable"
        if age >= DAMAGED_GRACE:
            return STALE, "damaged-for-%.0fs" % age
        return HELD, "damaged-within-grace"
    pid = holder.get("pid")
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return STALE, "no-pid"
    if pid <= 0:
        return STALE, "no-pid"
    state, token = _pid_identity(pid)
    if state == DEAD:
        return STALE, "dead-pid"
    if state == UNKNOWN:
        return UNKNOWN, "identity-unreadable"
    recorded = holder.get("pid_started")
    if recorded and token and token != recorded:
        return STALE, "pid-recycled (recorded %s, now %s)" % (recorded, token)
    if recorded and not token:
        # Alive, but this reader cannot obtain the stamp needed to compare
        # against what the holder wrote down. Unproven is not stale.
        return UNKNOWN, "identity-unreadable"
    if _created_after_the_lock(file_path, token):
        return STALE, "pid-recycled (created after the lock file was written)"
    if not recorded:
        # An old-format lock, or a platform with no obtainable stamp. The strong
        # check did not run and the reader is told so by name, because a reason
        # that hides a degraded check is worse than no reason.
        return HELD, "pid-only-no-recorded-identity"
    return HELD, "identity-matches"


def _takeable(file_path, holder):
    """May this lock be taken over as stale? ONLY when it is provably STALE.

    UNKNOWN is not takeable. That is the whole difference from the version this
    replaces, which asked `_alive(pid)` and so answered "held" for a recycled
    number and "takeable" for a pid it merely could not read.
    """
    return holder_state(file_path, holder)[0] == STALE


def _label(branch):
    """What to record in the lock's `branch` field.

    MEASURED 2026-10-02. `scripts/run_suite.py` resolves the branch with
    `git rev-parse --abbrev-ref HEAD`, which answers the literal string "HEAD" for
    a DETACHED worktree - and the reference run, the merge gate and every baseline
    run are detached on purpose, because a frozen checkout at a named SHA is the
    only honest reference. So the one field that exists to tell a waiting run who
    is ahead of it said "HEAD", and three separate agents went looking for the
    holder by hand. A detached checkout is named by its commit instead.
    """
    text = (branch or "").strip()
    if text and text != "HEAD":
        return text
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True, timeout=20,
                             check=False)
        sha = (out.stdout or "").strip()
    except Exception:                                          # noqa: BLE001
        sha = ""
    # Only "HEAD" and the empty string reach this line, and NEITHER may be
    # returned. `None` says "unknown", which is true; "HEAD" says something false
    # about a real branch, and this module's own rule is that an authority which
    # cannot be read is UNKNOWN rather than an answer. My first version returned
    # `text or None` here and handed back "HEAD" - the exact defect being fixed,
    # reintroduced in the fix, and caught by the test below rather than by review.
    return ("detached %s" % sha) if sha else None


def _queue_dir(file_path):
    return file_path + QUEUE_SUFFIX


def _ticket_name(pid=None):
    """A name whose LEXICOGRAPHIC order is its chronological order.

    Fixed-width seconds, so there is no shorter-string-sorts-first surprise, then
    the pid as a deterministic tiebreak for two waiters inside the same microsecond.
    """
    return "%020.6f-%d.json" % (time.time(),
                                os.getpid() if pid is None else pid)


def _take_ticket(file_path, payload, say=print):
    """Join the queue. Returns the ticket path, or None if ticketing is impossible.

    None is not an error and must not stop a run: it degrades `acquire` to the
    unordered race, which still serialises.
    """
    try:
        directory = _queue_dir(file_path)
        os.makedirs(directory, exist_ok=True)
        ticket = os.path.join(directory, _ticket_name())
        handle = os.open(ticket, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        try:
            os.write(handle, json.dumps(payload, sort_keys=True).encode("utf-8"))
        finally:
            os.close(handle)
        return ticket
    except Exception:                                          # noqa: BLE001
        say("suite.lock: could not join the ticket queue, so this run competes "
            "unordered. Serialisation still holds; fairness does not.")
        return None


def _pid_of_ticket(name):
    """The pid a ticket name carries, or None when it is not one of ours."""
    base = os.path.basename(name)
    stem = base[:-5] if base.endswith(".json") else base
    _, dash, pid = stem.rpartition("-")
    if not dash:
        return None
    try:
        return int(pid)
    except ValueError:
        return None


def _live_tickets(file_path):
    """Queued tickets whose owner is still running, in arrival order.

    A dead owner's ticket is deleted as it is found, so a waiter that crashed
    cannot wedge the queue behind it forever. A file that is NOT one of our
    tickets is left alone rather than deleted - this directory is not ours to
    tidy, and deleting an unknown file is how a lock loses somebody else's state.
    """
    try:
        names = sorted(os.listdir(_queue_dir(file_path)))
    except Exception:                                          # noqa: BLE001
        return []
    out = []
    for name in names:
        full = os.path.join(_queue_dir(file_path), name)
        pid = _pid_of_ticket(name)
        if pid is None:
            continue
        if not _alive(pid):
            try:
                os.unlink(full)
            except OSError:
                pass
            continue
        out.append(full)
    return out


def _my_turn(file_path, ticket):
    """May this run attempt the lock yet?

    True when it holds the earliest live ticket. Two cases deliberately answer
    True rather than waiting, because a queue that can DEADLOCK is worse than one
    that is merely unfair: no ticket at all (the documented fallback), and a ticket
    that has vanished from disk - if anything pruned ours by mistake, waiting for a
    turn that can never come would park the run until its timeout and then refuse.
    """
    if ticket is None:
        return True
    if not os.path.exists(ticket):
        return True
    live = _live_tickets(file_path)
    if not live:
        return True
    return os.path.abspath(live[0]) == os.path.abspath(ticket)


def _drop_ticket(ticket):
    if not ticket:
        return
    try:
        os.unlink(ticket)
    except OSError:
        pass


def acquire(branch=None, timeout=DEFAULT_TIMEOUT, file_path=None, poll=POLL,
            say=print):
    """Take the lock, waiting for whoever holds it, IN ARRIVAL ORDER.

    Returns the payload written. Raises `SuiteBusy` if the lock was not obtained
    inside `timeout`. Does NOT raise when the holder is dead: that lock is stale,
    and the takeover is announced with the dead PID so a reader can see it.
    """
    file_path = file_path or path()
    # TWO TIMES, BECAUSE THEY ARE TWO DIFFERENT FACTS. `started_at` used to be
    # stamped HERE, before the wait, so it recorded when the process was LAUNCHED
    # and never when it took the lock. Measured 2026-10-02 by the run it misled:
    # the lock claimed `started_at=15:20:52` while that suite actually ran
    # 15:59:58 to 16:39:12 - a 39-minute overstatement, exactly its queue wait -
    # and `wt-osauth` was at one point advertising a ~77-minute overstatement.
    #
    # That number is printed in all three operator-facing messages: the waiting
    # announcement, the `SuiteBusy` refusal and the stale-takeover line. A reader
    # asking "is this hung?" saw a 40-minute suite apparently 77 minutes in, and
    # the obvious response to that is to kill a perfectly healthy run - which is
    # the exact mistake that cost this project time earlier the same day, except
    # here the lock itself was supplying the misleading figure.
    #
    # `queued_at` keeps the old number under an honest name, so the wait is still
    # visible, and `started_at` is stamped at the moment the write succeeds.
    #
    # AND THE CREATION STAMP, WHICH IS THE ONLY FIELD HERE THAT IS AN IDENTITY.
    # Every other one can be recycled, reused or written by hand: `pid` is a slot
    # the OS re-issues, `branch` and `worktree` repeat across runs, and the two
    # timestamps are naive local strings. `pid_started` is read from the kernel
    # for this process and cannot be chosen by it. `identity` names which
    # guarantee this lock actually carries, so a reader never has to infer that
    # from the presence or absence of a field.
    _own_state, _own_token = _pid_identity(os.getpid())
    mine = {"pid": os.getpid(), "branch": _label(branch),
            "pid_started": _own_token,
            "identity": "pid+created" if _own_token else "pid-only",
            "worktree": os.path.abspath(os.getcwd()),
            "queued_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "started_at": None,
            "lock_path": file_path}
    ticket = _take_ticket(file_path, mine, say=say)
    deadline = time.monotonic() + float(timeout)
    announced = False
    queued = False
    try:
        while True:
            if _my_turn(file_path, ticket):
                # Stamped per attempt, so the value that lands in the file is
                # the moment this run actually took the lock.
                mine["started_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
                try:
                    _write(file_path, mine)
                    return mine
                except FileExistsError:
                    pass
                holder = read(file_path) or {}
                state, reason = holder_state(file_path, holder)
                if state == STALE:
                    say("suite.lock: the holder is gone, taking over a stale lock "
                        f"(reason={reason}, pid={holder.get('pid')!r}, "
                        f"branch={holder.get('branch')!r}, "
                        f"started_at={holder.get('started_at')!r})")
                    try:
                        os.unlink(file_path)
                    except FileNotFoundError:
                        pass
                    continue
                if not announced:
                    say(f"suite.lock: waiting for pid={holder.get('pid')} "
                        f"branch={holder.get('branch')!r} "
                        f"holding since {holder.get('started_at')} "
                        f"(queued at {holder.get('queued_at')}) "
                        f"[{state}: {reason}] - one full suite "
                        f"runs on this machine at a time")
                    announced = True
            elif not queued:
                live = _live_tickets(file_path)
                try:
                    place = live.index(os.path.abspath(ticket)) + 1
                except ValueError:
                    place = len(live) + 1
                say(f"suite.lock: queued at position {place} of {len(live)}, in "
                    f"arrival order. Waiting my turn rather than racing for it.")
                queued = True
            if time.monotonic() >= deadline:
                holder = read(file_path) or {}
                state, reason = holder_state(file_path, holder)
                raise SuiteBusy(
                    f"did not get {file_path} within {timeout:.0f}s. Holder: "
                    f"pid={holder.get('pid')} branch={holder.get('branch')!r} "
                    f"holding since {holder.get('started_at')} "
                    f"(queued at {holder.get('queued_at')}) "
                    f"[{state}: {reason}]; "
                    f"{len(_live_tickets(file_path))} run(s) in the queue. Not "
                    f"starting in parallel - six concurrent suites on 2026-10-02 "
                    f"made every one of them untrustworthy.")
            time.sleep(min(float(poll), max(0.0, deadline - time.monotonic())))
    finally:
        # Dropped on EVERY exit - grant, refusal or exception. A ticket left
        # behind would hold the queue against every later arrival until this PID
        # died, which is the starvation this function exists to remove.
        _drop_ticket(ticket)


def release(file_path=None):
    """Drop the lock, but ONLY if this process holds it.

    Returns True when a lock was removed. A lock held by somebody else is left
    alone and False is returned: a run that crashed and restarted must not delete
    the lock of the run that took over from it.
    """
    file_path = file_path or path()
    holder = read(file_path)
    if not holder:
        return False
    if holder.get("pid") != os.getpid():
        return False
    # THE SAME DEFECT, ON THE DESTRUCTIVE SIDE, and nothing named it before.
    # PID equality was the ONLY guard here, so once the OS recycled a lock
    # holder's number onto this process, this function would delete a LIVE
    # suite's lock and report success. The recorded stamp closes it: if the lock
    # says it was taken by a process created at some other moment, it is not
    # ours to remove, however much the numbers agree.
    recorded = holder.get("pid_started")
    if recorded:
        _state, token = _pid_identity(os.getpid())
        if token is not None and token != recorded:
            return False
    try:
        os.unlink(file_path)
    except FileNotFoundError:
        return False
    return True
