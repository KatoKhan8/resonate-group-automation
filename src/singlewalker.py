"""One walker per job, enforced by the filesystem.

WHY THIS EXISTS. On 2026-09-22 two `learning_walk_replies.py` processes ran
against one cursor and one append-mode file. A second walker does not walk
twice as fast - it re-walks the same pages and writes every row again. The
result was 32,025 rows in a 16,650-row file, and **the duplication was
invisible in the job's own state**, which counts only what that process
fetched. The file is what analysis reads, so the file was wrong while every
number the job reported about itself was right.

`os.O_EXCL` is the whole mechanism: the create succeeds for exactly one
process. A lock whose holder is gone is stale - a killed walker never unlinks
- so that case is reclaimed rather than blocking the estate on a dead pid.

`scripts/learning_walk_replies.py` carries its own copy of this, written
first and left alone because the process was mid-walk when this module was
extracted. It should import from here the next time it is restarted.
"""
import os
import subprocess


class AlreadyWalking(RuntimeError):
    """A second walker refused. Not a condition to recover from - a refusal."""


def _alive(pid):
    if os.name == "nt":
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}"],
                             capture_output=True, text=True).stdout
        return str(pid) in out
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def acquire(path):
    """Take the lock at `path`, or raise `AlreadyWalking`."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    while True:
        try:
            handle = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                with open(path, encoding="utf-8") as existing:
                    pid = int((existing.read() or "0").strip() or 0)
            except (OSError, ValueError):
                pid = 0
            if pid and _alive(pid):
                raise AlreadyWalking(
                    f"another walker holds {path} (pid {pid}). One walker "
                    "only: a second re-walks the same pages into the same "
                    "file, and the job's own state cannot see it happening.")
            os.unlink(path)
            continue
        with os.fdopen(handle, "w") as out:
            out.write(str(os.getpid()))
        return


def release(path):
    try:
        os.unlink(path)
    except OSError:
        pass


class held:
    """Context manager: `with singlewalker.held(LOCK): ...`"""

    def __init__(self, path):
        self.path = path

    def __enter__(self):
        acquire(self.path)
        return self

    def __exit__(self, *_exc):
        release(self.path)
        return False
