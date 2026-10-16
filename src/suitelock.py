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

AND A PID IS NOT AN IDENTITY - TASK 0399, measured 2026-10-16. The sentence above
was the whole rule and it is not sufficient: Windows recycles PIDs, so the number
in the lock can be handed to an unrelated process at any moment.
`suppression/0395` got two opposite liveness answers for the same number four
minutes apart, because 79548 had been recycled onto one of its own shell's
transient processes. Both directions are wrong: a dead holder's recycled number
reads HELD and parks every lane behind a ghost, and the same coincidence in
reverse lets a live holder's lock be taken when the recycled process exits. The
lock now records `pid_created`, an opaque process start stamp read from the OS,
and `holder_state` has a THIRD answer - UNIDENTIFIABLE - which is never takeable
at any age, because a legitimate suite may run 150 minutes and age is therefore
evidence of nothing.

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


#: The three answers the reader has about a recorded holder, and the reason
#: this is not a boolean. TASK 0399.
#:
#: MEASURED 2026-10-16. `_alive` is correct about the PID and the PID is not
#: the holder: `suppression/0395` got two opposite liveness answers for the
#: same number four minutes apart, because 79548 had been recycled onto one
#: of its own shell's transient processes. A stale-lock check that consults
#: `_alive(pid)` alone therefore answers "held, keep waiting" the moment the
#: OS hands that number to anything at all - and the suite is the merge
#: gate's only instrument, so that blocks every lane at once. The same number
#: read the other way is worse: a dead holder whose PID has been reused by a
#: process that then exits would be taken over correctly by luck.
#:
#: HELD and STALE are the two the old reader had. UNIDENTIFIABLE is the one
#: it did not, and it FAILS CLOSED: a reader that cannot establish whether
#: the live PID is the holder WAITS. Fail-open here means two suites writing
#: one evidence path, which is how 91 of 227 names were destroyed with
#: neither writer learning.
HELD = "held"
STALE = "stale"
UNIDENTIFIABLE = "unidentifiable"

#: `OpenProcess` access right that is enough for `GetProcessTimes` and
#: `GetExitCodeProcess` and NOT enough to affect the process. Measured on
#: this machine 2026-10-16: it answers for a same-user process this reader
#: did not create - including the suite lock's own live holder - and it is
#: refused with ERROR_ACCESS_DENIED for all eight SYSTEM-owned processes
#: probed, which is the UNIDENTIFIABLE branch arriving from the real world
#: rather than from a test.
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
STILL_ACTIVE = 259
_ERROR_INVALID_PARAMETER = 87
_ERROR_ACCESS_DENIED = 5


class _FILETIME(ctypes.Structure):
    _fields_ = [("dwLowDateTime", ctypes.c_uint32),
                ("dwHighDateTime", ctypes.c_uint32)]


def process_identity(pid):
    """`(state, created, detail)` for one PID. State is ALIVE/GONE/UNKNOWN.

    `created` is an opaque, comparable integer that identifies the PROCESS
    rather than the number: on Windows the creation FILETIME, 100ns since
    1601, read through `GetProcessTimes`; on Linux field 22 of
    `/proc/<pid>/stat`, the start time in clock ticks since boot. Both are
    stable for the life of the process - MEASURED across the alive-to-dead
    transition, where the value did not move - and both are distinct for two
    processes of the same executable started 1.1s apart (11,032,755 ticks).
    Nothing derives it from the clock here, because a reader that recomputes
    an identity cannot detect the one thing it exists to detect.

    WHY NOT A BOOT ID AS WELL. The Windows value is an absolute wall-clock
    instant at 100ns resolution, so a post-reboot process would have to be
    created at the identical instant for the pair to collide. The Linux value
    is boot-relative, so there the PAIR is unique per boot and a reboot
    resets both the PIDs and the counter - which is the same guarantee
    reached differently. Stated rather than assumed, because "PID plus start
    time" is the usual answer and the usual answer is not a measurement.

    UNKNOWN IS A REAL ANSWER and every caller must fail closed on it.
    """
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return "GONE", None, "the recorded pid is not a number: %r" % (pid,)
    if pid <= 0:
        return "GONE", None, "the recorded pid is not positive"
    if os.name == "nt":
        return _identity_nt(pid)
    return _identity_proc(pid)


def _identity_nt(pid):
    try:
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        handle = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False,
                                 pid)
    except Exception as exc:                                   # noqa: BLE001
        return "UNKNOWN", None, "OpenProcess unavailable: %s" % exc
    if not handle:
        err = ctypes.get_last_error()
        if err == _ERROR_INVALID_PARAMETER:
            # The documented answer for a PID that does not exist. Measured.
            return "GONE", None, "OpenProcess ERROR_INVALID_PARAMETER (87)"
        if err == _ERROR_ACCESS_DENIED:
            return "UNKNOWN", None, "OpenProcess ERROR_ACCESS_DENIED (5)"
        return "UNKNOWN", None, "OpenProcess failed, WinError %d" % err
    try:
        creation, exited, kernel, user = (_FILETIME(), _FILETIME(),
                                          _FILETIME(), _FILETIME())
        if not k32.GetProcessTimes(handle, ctypes.byref(creation),
                                   ctypes.byref(exited),
                                   ctypes.byref(kernel), ctypes.byref(user)):
            return ("UNKNOWN", None, "GetProcessTimes failed, WinError %d"
                    % ctypes.get_last_error())
        created = (creation.dwHighDateTime << 32) | creation.dwLowDateTime
        code = ctypes.c_uint32()
        if not k32.GetExitCodeProcess(handle, ctypes.byref(code)):
            return ("UNKNOWN", created, "GetExitCodeProcess failed, WinError "
                    "%d" % ctypes.get_last_error())
        if code.value == STILL_ACTIVE:
            return "ALIVE", created, "STILL_ACTIVE"
        # A HANDLE OUTLIVES ITS PROCESS, and `GetProcessTimes` still answers
        # for a dead one - measured: the creation time of an exited child was
        # still readable and identical. Without the exit code this reader
        # would call a corpse ALIVE, which is the failure it replaces.
        return "GONE", created, "exited with code %d" % code.value
    finally:
        try:
            k32.CloseHandle(handle)
        except Exception:                                      # noqa: BLE001
            pass


def _identity_proc(pid):
    """Linux: field 22 of `/proc/<pid>/stat`. Elsewhere: UNKNOWN, honestly."""
    path_ = "/proc/%d/stat" % pid
    if not os.path.exists("/proc"):
        return ("UNKNOWN", None,
                "no /proc on this platform, so no process start time is "
                "available to this reader")
    try:
        with open(path_, encoding="utf-8", errors="replace") as handle:
            text = handle.read()
    except FileNotFoundError:
        return "GONE", None, "no %s" % path_
    except Exception as exc:                                   # noqa: BLE001
        return "UNKNOWN", None, "could not read %s: %s" % (path_, exc)
    # The comm field is parenthesised and may contain spaces, so the split
    # starts after the last ')'.
    tail = text[text.rfind(")") + 1:].split()
    try:
        # stat fields are 1-based and field 3 is `state`; after the comm
        # split, `tail[0]` IS field 3, so field 22 is index 19.
        return "ALIVE", int(tail[19]), "/proc stat starttime"
    except (IndexError, ValueError):
        return ("UNKNOWN", None,
                "%s did not carry a parsable starttime" % path_)


def holder_state(holder, file_path=None):
    """`(HELD | STALE | UNIDENTIFIABLE, reason)` for a recorded holder.

    The ONE reader every caller asks. Deliberately ordered:

    1. A lock whose CONTENT could not be read keeps `DAMAGED_GRACE`
       unchanged - that window exists for the fallback publish path.
    2. A pid that is not running at all is STALE. Checked BEFORE the
       identity, and with `_alive`, so a lock written by a version that
       recorded no identity is still recovered without a human on every
       platform. That is the old behaviour, kept.
    3. A pid that IS running and whose recorded identity MATCHES is HELD.
    4. A pid that is running and whose recorded identity DIFFERS is STALE,
       and the reason says the number was recycled.
    5. A pid that is running whose identity cannot be obtained - or a lock
       that records none - is UNIDENTIFIABLE, and UNIDENTIFIABLE IS NOT
       TAKEABLE. Age does not change that: a legitimate suite may run 150
       minutes, so a long hold is not evidence of anything.
    """
    pid = holder.get("pid")
    if holder.get("damaged"):
        try:
            age = time.time() - os.path.getmtime(file_path or path())
        except OSError:
            return STALE, "the lock is unreadable and has no mtime"
        if age >= DAMAGED_GRACE:
            return STALE, ("the lock has been unreadable for %.0fs, longer "
                           "than the %.0fs grace" % (age, DAMAGED_GRACE))
        return HELD, ("the lock is unreadable but only %.0fs old; the atomic "
                      "publish makes that a window, not a corpse" % age)
    if not _alive(pid):
        return STALE, "the recorded pid %r is not running" % (pid,)
    recorded = holder.get("pid_created")
    state, created, detail = process_identity(pid)
    if state == "GONE":
        return STALE, ("pid %r is gone (%s); `_alive` disagreed and the "
                       "identity reader is the stronger witness"
                       % (pid, detail))
    if state != "ALIVE":
        return UNIDENTIFIABLE, ("pid %r is running but its identity cannot "
                                "be read (%s), so whether it is the holder "
                                "is UNKNOWN - waiting, not stealing"
                                % (pid, detail))
    if recorded is None:
        return UNIDENTIFIABLE, ("pid %r is running and this lock records no "
                                "`pid_created` (written before TASK 0399), "
                                "so a holder cannot be told from a recycled "
                                "number - waiting, not stealing" % (pid,))
    if created != recorded:
        return STALE, ("pid %r is alive but is NOT the holder: the lock "
                       "records a process created at %r and the process now "
                       "holding that number was created at %r. The number "
                       "was recycled." % (pid, recorded, created))
    return HELD, "pid %r was created at %r, which matches the lock" % (
        pid, recorded)


def _alive(pid):
    """Is this PID running? Unknown counts as ALIVE, so a lock is never stolen
    on a guess - waiting costs time, stealing costs a corrupted run.

    KEPT, AND NO LONGER THE WHOLE ANSWER. TASK 0399: this function is sound
    about a NUMBER and a number is not a process. `holder_state` is what
    decides whether a lock may be taken; this is one of its inputs, and it
    is also what prunes the ticket queue, where a wrong answer costs
    fairness rather than safety.

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
    """May this lock be taken over as stale? One reader, three answers.

    TASK 0399: this used to BE the decision, and it decided on
    `_alive(holder["pid"])` alone - so a recycled PID read as a live holder
    and a dead holder's recycled number could be stolen from. The decision
    now lives in `holder_state`, which has a third answer, and only STALE is
    takeable. UNIDENTIFIABLE is not: the caller waits.
    """
    return holder_state(holder, file_path)[0] == STALE


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
    # `pid_created` IS THE IDENTITY, and the pid alone was never one. TASK
    # 0399: of the six fields this payload used to carry, not one identified
    # a process - `pid` is recycled by the OS, `branch` is free text,
    # `worktree` is shared by every run from that tree, and the two
    # timestamps are local-clock strings with no timezone. A reader could
    # only ever ask `_alive(pid)`. The value is read from the OS, never
    # computed from the clock, because an identity a reader can recompute
    # cannot detect the thing it exists to detect. `None` when this platform
    # will not say, which `holder_state` treats as UNIDENTIFIABLE rather
    # than as agreement.
    mine = {"pid": os.getpid(), "branch": _label(branch),
            "pid_created": process_identity(os.getpid())[1],
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
                state, why = holder_state(holder, file_path)
                if state == STALE:
                    say("suite.lock: taking over a stale lock - "
                        f"{why} (branch={holder.get('branch')!r}, "
                        f"started_at={holder.get('started_at')!r})")
                    try:
                        os.unlink(file_path)
                    except FileNotFoundError:
                        pass
                    continue
                if not announced:
                    # The verdict is printed, not just the holder. A reader
                    # asking "why am I waiting" could previously not tell a
                    # live suite from a number nobody could identify, and
                    # those two need different actions from a human.
                    say(f"suite.lock: {state} - {why}. Waiting: "
                        f"branch={holder.get('branch')!r} "
                        f"since {holder.get('started_at')} "
                        f"(queued at {holder.get('queued_at')}) - one full suite "
                        f"runs on this machine at a time")
                    if state == UNIDENTIFIABLE:
                        say("suite.lock: an UNIDENTIFIABLE holder is never "
                            "taken over automatically, at any age. If this "
                            "lock is in fact dead, a human has to look at it "
                            f"and remove {file_path}.")
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
                state, why = holder_state(holder, file_path)
                raise SuiteBusy(
                    f"did not get {file_path} within {timeout:.0f}s. "
                    f"Holder is {state}: {why}. "
                    f"pid={holder.get('pid')} branch={holder.get('branch')!r} "
                    f"holding since {holder.get('started_at')} "
                    f"(queued at {holder.get('queued_at')}); "
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
