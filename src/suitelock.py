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
"""
import json
import os
import subprocess
import time

#: How long a waiting run will sit before giving up. Longer than one full suite,
#: because waiting for the suite ahead of you is the normal case, not an error.
DEFAULT_TIMEOUT = 4200.0

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
    on a guess - waiting costs time, stealing costs a corrupted run."""
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


def _write(file_path, payload):
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    handle = os.open(file_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        os.write(handle, json.dumps(payload, sort_keys=True).encode("utf-8"))
    finally:
        os.close(handle)


def acquire(branch=None, timeout=DEFAULT_TIMEOUT, file_path=None, poll=POLL,
            say=print):
    """Take the lock, waiting for whoever holds it. Returns the payload written.

    Raises `SuiteBusy` if the holder is still alive after `timeout`. Does NOT
    raise when the holder is dead: that lock is stale, and the takeover is
    announced with the dead PID so a reader can see what happened.
    """
    file_path = file_path or path()
    mine = {"pid": os.getpid(), "branch": branch,
            "worktree": os.path.abspath(os.getcwd()),
            "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "lock_path": file_path}
    deadline = time.monotonic() + float(timeout)
    announced = False
    while True:
        try:
            _write(file_path, mine)
            return mine
        except FileExistsError:
            pass
        holder = read(file_path) or {}
        if not _alive(holder.get("pid")):
            say("suite.lock: the holder is gone, taking over a stale lock "
                f"(dead pid={holder.get('pid')!r}, "
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
                f"started_at={holder.get('started_at')} - one full suite runs on "
                f"this machine at a time")
            announced = True
        if time.monotonic() >= deadline:
            raise SuiteBusy(
                f"another suite still holds {file_path} after {timeout:.0f}s: "
                f"pid={holder.get('pid')} branch={holder.get('branch')!r} "
                f"started_at={holder.get('started_at')}. Not starting in "
                f"parallel - six concurrent suites on 2026-10-02 made every one "
                f"of them untrustworthy.")
        time.sleep(min(float(poll), max(0.0, deadline - time.monotonic())))


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
