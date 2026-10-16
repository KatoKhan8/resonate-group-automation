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

A PID PLUS ITS START TIME IS AN IDENTITY. A PID IS NOT. MEASURED 2026-10-16,
and it is the defect this file could not see. The lock named its holder by pid
alone, and Windows recycles pids: a writer that died at process start left a lock
that was held for 89 minutes by nothing, and a reader asking the same question
twice four minutes apart got two OPPOSITE answers, because the dead holder's
number had landed on an unrelated transient process. `_alive` was right both
times - the pid WAS alive the second time. The pid is not the holder. So the lock
now records the process's start time beside the pid, and `_holder_alive` calls a
holder live only when the pid is alive AND its start time is the one recorded.
The OS never reissues a pid with the same start time, so a recycled number can no
longer pass for the holder. Waiting behind a ghost is not recoverable by waiting,
and nothing in this estate would have reported it.

A LOCK CARRYING NO START TIME IS WAITED ON, NEVER STOLEN, and the argument is
worth stating because both readings are defensible. A lock written before
2026-10-16 records only a pid, so the identity it names CANNOT BE VERIFIED - that
is UNKNOWN, not a mismatch. This module already has a rule for an unknown
liveness answer, written into `_alive` itself: unknown counts as ALIVE, because
waiting costs time and stealing costs a corrupted run. Calling the missing field
a mismatch would have stolen the reference run that held the one live lock on
this machine while this change was being written, and no run can replace it. The
cost is bounded and named here rather than discovered: an OLD-FORMAT lock whose
holder is DEAD is also waited on, so it needs one hand deletion, and after this
change no new old-format lock can be written by anybody. The wait message says
`identity UNVERIFIED` when that is why it is waiting.
"""
import ctypes
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


def _alive(pid):
    """Is this PID running? Unknown counts as ALIVE, so a lock is never stolen
    on a guess - waiting costs time, stealing costs a corrupted run.

    MEASURED 2026-10-02, because it decides whether this whole module is sound:
    `tasklist` invoked through `subprocess`, as here, DOES answer correctly - a
    known-live pid comes back in the table and a nonexistent one produces the
    "No tasks are running" line. The same command typed into a Git Bash shell
    returns nothing at all for every query, which is how a live holder was briefly
    reported dead by a human reader. The reader here is not that one.
    """
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                                 capture_output=True, text=True, timeout=20,
                                 check=False)
        except Exception:                                      # noqa: BLE001
            return True
        return str(pid) in (out.stdout or "")
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except Exception:                                          # noqa: BLE001
        return True
    return True


#: `PROCESS_QUERY_LIMITED_INFORMATION`. Enough to read a start time and no more,
#: which is also why it succeeds against processes this user does not own.
_QUERY_LIMITED = 0x1000

#: The Win32 library, with its signatures pinned once. None until first use.
_nt_kernel32 = None


def _proc_start(pid):
    """When the process with this pid started, as an OPAQUE token - or None.

    A pid is a number the OS reissues; (pid, start time) is not, so this is what
    makes the holder an identity. NOTHING DECODES THE TOKEN - it is compared for
    equality against the value the lock recorded and is never read as a clock, so
    the Windows and POSIX forms do not have to mean the same thing, and a lock is
    only ever compared with a reading taken on the machine that wrote it.

    None means THIS MACHINE COULD NOT ANSWER - a dead pid, a process this user
    cannot open, a /proc that is not mounted - and is never "it did not match".
    The caller decides what an unanswerable identity means; see `_holder_alive`.
    """
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return None
    if pid <= 0:
        return None
    if os.name != "nt":
        try:
            with open("/proc/%d/stat" % pid, "rb") as handle:
                # Field 22 of 52, counting from 1. Split from the LAST ')' because
                # field 2 is the executable name, which may contain spaces and ')'
                # itself; after that split field 3 is index 0, so 22 is index 19.
                return handle.read().rsplit(b")", 1)[1].split()[19].decode()
        except Exception:                                      # noqa: BLE001
            return None
    global _nt_kernel32
    try:
        if _nt_kernel32 is None:
            lib = ctypes.WinDLL("kernel32", use_last_error=True)
            # ARGTYPES ARE NOT DECORATION. Without them ctypes passes a 64-bit
            # HANDLE as a 32-bit int and truncates it, so the call would ask
            # about a different process, or about none - and every answer here
            # would still look like a plausible start time.
            lib.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int,
                                        ctypes.c_uint32]
            lib.OpenProcess.restype = ctypes.c_void_p
            lib.GetProcessTimes.argtypes = [ctypes.c_void_p] * 5
            lib.GetProcessTimes.restype = ctypes.c_int
            lib.CloseHandle.argtypes = [ctypes.c_void_p]
            lib.CloseHandle.restype = ctypes.c_int
            _nt_kernel32 = lib
        handle = _nt_kernel32.OpenProcess(_QUERY_LIMITED, 0, pid)
        if not handle:
            return None
        try:
            # FILETIME is two DWORDs, which on this platform IS a little-endian
            # 64-bit value. All four out-parameters are required, and three are
            # not wanted.
            created = ctypes.c_ulonglong(0)
            spare = [ctypes.c_ulonglong(0) for _ in range(3)]
            ok = _nt_kernel32.GetProcessTimes(
                handle, ctypes.byref(created), ctypes.byref(spare[0]),
                ctypes.byref(spare[1]), ctypes.byref(spare[2]))
            if not ok:
                return None
            return "%d" % created.value
        finally:
            _nt_kernel32.CloseHandle(handle)
    except Exception:                                          # noqa: BLE001
        return None


def _holder_alive(holder):
    """Is the PROCESS THAT WROTE THIS LOCK still the one behind its pid?

    This is the question `_alive` cannot answer, and calling it is the whole fix.
    `_alive(pid)` asks "is a process with this number running?", which is true of
    the recycled number as readily as of the holder - measured 2026-10-16, when a
    dead holder's pid was briefly reused and the lock read LIVE for as long as
    nobody looked by hand.

    TWO UNKNOWNS BOTH COUNT AS ALIVE, and neither is a silent fallback. A lock
    from before 2026-10-16 records no start time; asking the OS can fail. In both
    cases the identity is UNVERIFIED rather than disproved, and an unverifiable
    holder is waited on - the same direction `_alive` already takes, because
    waiting costs time and stealing costs a corrupted run. Only a pid that is
    DEAD, or a start time that is READ AND DIFFERS, makes this False.
    """
    pid = holder.get("pid")
    if not _alive(pid):
        return False
    recorded = holder.get("proc_start")
    if recorded is None:
        return True
    now = _proc_start(pid)
    if now is None:
        return True
    return now == recorded


def _identity_note(holder):
    """One clause saying HOW this lock's holder was judged, for the messages a
    human reads when a run is waiting.

    It exists because the two failures are indistinguishable from outside and
    need different answers. A dead holder's lock is recoverable by waiting one
    poll - the takeover is automatic. A RECYCLED pid's lock is not recoverable by
    waiting at all, and before this change nothing in the estate reported it: the
    lock simply said somebody was still working.
    """
    if holder.get("proc_start") is None:
        return ("identity UNVERIFIED - this lock records no start time (the "
                "format before 2026-10-16), so a recycled pid cannot be told "
                "from the holder; delete it by hand only if the holder is known "
                "to be gone")
    pid = holder.get("pid")
    if not _alive(pid):
        return "holder pid is gone"
    if _proc_start(pid) != holder.get("proc_start"):
        return ("holder pid is ALIVE but its start time is not the one this lock "
                "recorded, so the pid has been RECYCLED - waiting cannot clear "
                "this and nothing else in the estate reports it")
    return "pid and start time both match"


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


def _takeable(file_path, holder):
    """May this lock be taken over as stale? Three cases, deliberately ordered.

    A holder that is still the process it says it is: never - waiting costs time,
    stealing costs a corrupted run. `_holder_alive` is the question, NOT
    `_alive`: a pid alone is a number the OS reissues, so a recycled one would
    otherwise hold this lock forever. A holder whose content could not be READ:
    only once it has been unreadable for longer than `DAMAGED_GRACE`, because the
    fallback write path leaves the file empty for a moment and stealing inside
    that window takes the lock from a running suite. A holder with a dead pid:
    yes, because a machine that lost power mid-suite must not need a human to
    delete a file.
    """
    if _holder_alive(holder):
        return False
    if holder.get("damaged"):
        try:
            age = time.time() - os.path.getmtime(file_path)
        except OSError:
            return True
        return age >= DAMAGED_GRACE
    return True


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

    THE OWNER IS JUDGED BY `_holder_alive`, NOT BY `_alive`, for the reason this
    module was changed on 2026-10-16 - and the ticket queue is where that defect
    bites hardest. A ticket carries the same payload the lock does, so a crashed
    waiter's ticket whose pid gets recycled is held to be live, and if it is the
    EARLIEST live ticket then `_my_turn` is False for every arrival behind it:
    the whole queue, not one waiter, waits out its full timeout behind a ghost.
    The ticket's own bytes are read for that judgement, so a ticket too damaged
    to read falls back to its NAME, which is all the pre-2026-10-16 queue ever
    carried - and an unverifiable owner still counts as live, as `_holder_alive`
    documents.
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
        holder = read(full)
        if not holder or holder.get("pid") != pid:
            holder = {"pid": pid}
        if not _holder_alive(holder):
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
    # `proc_start` is READ ONCE, HERE, and never again: it is this process's own
    # start time, so it is fixed for the life of the process, and a later reading
    # of our own pid could only ever agree or be wrong. It is what turns the pid
    # below from a reissued number into an identity - see `_holder_alive`.
    mine = {"pid": os.getpid(), "proc_start": _proc_start(os.getpid()),
            "branch": _label(branch),
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
                if _takeable(file_path, holder):
                    say("suite.lock: the holder is gone, taking over a stale lock "
                        f"({_identity_note(holder)}: "
                        f"pid={holder.get('pid')!r}, "
                        f"branch={holder.get('branch')!r}, "
                        f"started_at={holder.get('started_at')!r}, "
                        f"proc_start={holder.get('proc_start')!r})")
                    try:
                        os.unlink(file_path)
                    except FileNotFoundError:
                        pass
                    continue
                if not announced:
                    say(f"suite.lock: waiting for pid={holder.get('pid')} "
                        f"branch={holder.get('branch')!r} "
                        f"holding since {holder.get('started_at')} "
                        f"(queued at {holder.get('queued_at')}); "
                        f"{_identity_note(holder)} - one full suite "
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
                raise SuiteBusy(
                    f"did not get {file_path} within {timeout:.0f}s. Holder: "
                    f"pid={holder.get('pid')} branch={holder.get('branch')!r} "
                    f"holding since {holder.get('started_at')} "
                    f"(queued at {holder.get('queued_at')}); "
                    f"{_identity_note(holder)}; "
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
    try:
        os.unlink(file_path)
    except FileNotFoundError:
        return False
    return True
