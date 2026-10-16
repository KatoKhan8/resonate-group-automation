"""TASK-0399 controls: a PID is a slot, not an identity, and here is the proof.

Runs the five controls the task asks for and prints the CURRENT reader's verdict
beside the FIXED reader's for each. The "current" reader is not a reconstruction
written from memory: it is `src/suitelock.py` as it stands at blob 12de2433e,
which is the byte-identical blob at HEAD, local `master`, `origin/master`,
`b1f290c84` and the main checkout's own branch tip - extracted with `git show`
and imported as a module. Pass its path with `--before`.

NOTHING HERE TOUCHES THE MACHINE-WIDE LOCK. Every constructed lock lives in a
fresh `tempfile.mkdtemp()`, and the one real lock that is consulted (C5) is
opened READ-ONLY, via `holder_state`, which stats and parses and writes nothing.

Usage:
    py -3 scripts/suitelock_recycle_controls.py --before <path-to-pre-fix-module>
"""
import argparse
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src import suitelock                                      # noqa: E402

#: A child that takes a FIXTURE lock for real and then either holds it or dies
#: without releasing. `os._exit` is the point of the second mode: it skips every
#: `finally`, which is exactly what a `0xC0000409` stack buffer overrun does to
#: `run_suite.py`'s `finally: suitelock.release()`.
CHILD = '''import os, sys, time
sys.path.insert(0, sys.argv[1])
from src import suitelock
suitelock.acquire(branch=sys.argv[3], file_path=sys.argv[2], timeout=10,
                  say=lambda *a, **k: None)
if sys.argv[4] == "die-at-start":
    os._exit(3221225794 & 0xFF)
sys.stdout.write("holding\\n")
sys.stdout.flush()
time.sleep(float(sys.argv[4]))
'''


def load_before(path):
    spec = importlib.util.spec_from_file_location("suitelock_before", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def lockdir():
    return os.path.join(tempfile.mkdtemp(prefix="t0399-"), "work")


def verdicts(before, file_path, label):
    """Print both readers' answers for the same lock file, side by side."""
    holder_before = before.read(file_path) or {}
    holder_after = suitelock.read(file_path) or {}
    old = before._takeable(file_path, holder_before)
    state, reason = suitelock.holder_state(file_path, holder_after)
    new = suitelock._takeable(file_path, holder_after)
    print("  %-22s %-28s %s" % (
        "CURRENT reader:",
        "HELD (keep waiting)" if not old else "STALE (take it over)",
        "_takeable=%s" % old))
    print("  %-22s %-28s %s" % (
        "FIXED reader:",
        "%s (%s)" % ("HELD (keep waiting)" if state == suitelock.HELD else
                     "STALE (take it over)" if state == suitelock.STALE else
                     "UNKNOWN (keep waiting)", reason),
        "_takeable=%s" % new))
    return old, new, state, reason


def spawn_child(file_path, branch, mode):
    """Start a child that really acquires `file_path`. Returns the Popen."""
    helper = os.path.join(os.path.dirname(file_path), "child.py")
    with open(helper, "w", encoding="utf-8") as handle:
        handle.write(CHILD)
    proc = subprocess.Popen([sys.executable, helper, ROOT, file_path, branch,
                             mode], stdout=subprocess.PIPE)
    return proc


def c1_recycled_pid_is_reachable(before):
    print("=" * 78)
    print("C1  A RECYCLED PID IS READ AS A LIVE HOLDER BY THE CURRENT READER")
    print("=" * 78)
    out = {}

    # --- C1a: the lock RECORDS a creation stamp, and it disagrees. -----------
    directory = lockdir()
    os.makedirs(directory, exist_ok=True)
    strong = os.path.join(directory, "suite.lock")
    victim = subprocess.Popen([sys.executable, "-c",
                               "import time; time.sleep(120)"])
    try:
        _state, token_now = suitelock._pid_identity(victim.pid)
        # The ghost lock: it claims to have been taken by this pid, but by a
        # process created at a different moment. Forged by hand here; produced
        # by the OS reissuing the number in the field.
        forged = "ft:%d" % (int(token_now[3:]) - 10_000_000_000)
        with open(strong, "w", encoding="utf-8") as handle:
            json.dump({"pid": victim.pid, "branch": "the-ghost-of-0395",
                       "pid_started": forged, "identity": "pid+created",
                       "queued_at": "2026-10-16T15:10:00",
                       "started_at": "2026-10-16T15:10:00"}, handle)
        print("\n  C1a  a lock recording a creation stamp that disagrees")
        print("       pid %d is LIVE and is `python -c sleep 120`, not a suite"
              % victim.pid)
        print("       recorded stamp %s" % forged)
        print("       actual   stamp %s" % token_now)
        out["c1a"] = verdicts(before, strong, "c1a")
    finally:
        victim.kill()
        victim.wait()

    # --- C1b: the lock records NO stamp. The 0395 case, and today's lock. ----
    # No timestamp is manipulated here. The lock is written FIRST, the clock is
    # allowed to pass the 5s slack, and only THEN is the process created - which
    # is the real sequence: the ghost was written at 15:10 and the number was
    # reissued later.
    directory = lockdir()
    os.makedirs(directory, exist_ok=True)
    weak = os.path.join(directory, "suite.lock")
    with open(weak, "w", encoding="utf-8") as handle:
        json.dump({"pid": None, "branch": "the-ghost-of-0395",
                   "queued_at": "2026-10-16T15:10:00",
                   "started_at": "2026-10-16T15:10:00"}, handle)
    written = os.path.getmtime(weak)
    print("\n  C1b  an OLD-FORMAT lock with no recorded stamp - the real case")
    print("       lock written at %.3f, then %gs pass, then the pid appears"
          % (written, suitelock.CLOCK_SLACK + 1))
    time.sleep(suitelock.CLOCK_SLACK + 1)
    victim = subprocess.Popen([sys.executable, "-c",
                               "import time; time.sleep(120)"])
    try:
        _state, token_now = suitelock._pid_identity(victim.pid)
        created = int(token_now[3:]) / 1e7 - suitelock.FILETIME_EPOCH_DELTA
        payload = json.load(open(weak, encoding="utf-8"))
        payload["pid"] = victim.pid
        with open(weak, "w", encoding="utf-8") as handle:
            json.dump(payload, handle)
        os.utime(weak, (written, written))   # keep the ORIGINAL write time
        print("       pid %d created %+.3fs RELATIVE to the lock file - after "
              "it, so it\n       cannot be the holder, whatever the lock says"
              % (victim.pid, created - written))
        out["c1b"] = verdicts(before, weak, "c1b")
    finally:
        victim.kill()
        victim.wait()
    return out


def c2_a_live_holder_is_respected(before):
    print()
    print("=" * 78)
    print("C2  A GENUINELY LIVE HOLDER IS STILL RESPECTED")
    print("=" * 78)
    directory = lockdir()
    os.makedirs(directory, exist_ok=True)
    file_path = os.path.join(directory, "suite.lock")
    child = spawn_child(file_path, "a-real-live-holder", "120")
    try:
        child.stdout.readline()                      # it has the lock
        holder = suitelock.read(file_path) or {}
        print("\n       pid %s took this lock itself, by calling acquire()"
              % holder.get("pid"))
        print("       identity=%r  pid_started=%r"
              % (holder.get("identity"), holder.get("pid_started")))
        out = verdicts(before, file_path, "c2")
        print("\n       And acquire() refuses rather than taking it:")
        try:
            suitelock.acquire(branch="a-second-suite", timeout=0.3,
                              file_path=file_path, poll=0.05,
                              say=lambda line: print("         say:", line))
            print("         !! TOOK THE LOCK - the instrument is broken")
        except suitelock.SuiteBusy as exc:
            print("         SuiteBusy: %s" % str(exc)[:150])
        return out
    finally:
        child.kill()
        child.wait()


def c3_died_at_start_is_reachable(before):
    print()
    print("=" * 78)
    print("C3  DIED-AT-PROCESS-START IS REACHABLE, AND NAMED, NOT AGED")
    print("=" * 78)
    directory = lockdir()
    os.makedirs(directory, exist_ok=True)
    file_path = os.path.join(directory, "suite.lock")
    log = os.path.join(directory, "suite_run.log")
    started = time.time()
    child = spawn_child(file_path, "died-at-start", "die-at-start")
    child.wait()
    wall = time.time() - started
    open(log, "w", encoding="utf-8").close()         # the 0-byte log
    holder = suitelock.read(file_path) or {}
    print("\n       the child acquired the lock and then os._exit()ed, which is"
          "\n       what 0xC0000409 does to run_suite's `finally: release()`")
    # The MEASURED wall, not the 0.0 the real artefact carried. The real run's
    # 0.0 was the watcher's figure for a process that never reached any test;
    # here the same shape costs one interpreter start, so it is a few tenths
    # rather than zero. Printing the measured number keeps the two apart.
    print("       exit_code=%s  measured wall_seconds=%.2f  log bytes=%d  "
          "(the real artefact: exit 3221225794, wall 0.0, 0-byte log)"
          % (child.returncode, wall, os.path.getsize(log)))
    print("       lock pid=%s is now dead; lock file AGE=%.1fs - seconds, not "
          "minutes,\n       so nothing here can be classified by age"
          % (holder.get("pid"), time.time() - os.path.getmtime(file_path)))
    out = verdicts(before, file_path, "c3")
    print("\n       the reason is named: %r"
          % (suitelock.holder_state(file_path, holder)[1],))
    return out


def c4_unobtainable_identity_waits(before):
    print()
    print("=" * 78)
    print("C4  IDENTITY UNOBTAINABLE -> WAIT. NEVER TAKE.")
    print("=" * 78)
    # A REAL unobtainable identity, not a mock: a protected system process. Its
    # pid is in use, so it is not dead, and `OpenProcess` returns ACCESS_DENIED,
    # so it cannot be identified either.
    query = ("Get-CimInstance Win32_Process | Where-Object { $_.Name -in "
             "@('csrss.exe','wininit.exe','services.exe') } | "
             "Select-Object -First 1 -ExpandProperty ProcessId")
    found = subprocess.run(["powershell", "-NoProfile", "-Command", query],
                           capture_output=True, timeout=120)
    text = found.stdout.decode("utf-8", "replace").strip()
    if not text.isdigit():
        print("\n       SKIPPED: no protected process found to borrow a pid from")
        return None
    protected = int(text)
    directory = lockdir()
    os.makedirs(directory, exist_ok=True)
    file_path = os.path.join(directory, "suite.lock")
    with open(file_path, "w", encoding="utf-8") as handle:
        json.dump({"pid": protected, "branch": "identity-unreadable",
                   "queued_at": "2026-10-16T15:10:00",
                   "started_at": "2026-10-16T15:10:00"}, handle)
    print("\n       pid %d is a protected system process. OpenProcess fails "
          "with 5,\n       ACCESS_DENIED: the number is IN USE and its identity"
          " is UNREADABLE." % protected)
    print("       _pid_identity -> %r" % (suitelock._pid_identity(protected),))
    out = verdicts(before, file_path, "c4")
    print("\n       and acquire() waits it out rather than stealing:")
    try:
        suitelock.acquire(branch="would-be-thief", timeout=0.3,
                          file_path=file_path, poll=0.05,
                          say=lambda line: print("         say:", line))
        print("         !! TOOK THE LOCK - fail-open, which is the 91-of-227 "
              "defect")
    except suitelock.SuiteBusy as exc:
        print("         SuiteBusy: %s" % str(exc)[:200])
    return out


def c5_age_alone_is_never_sufficient(before):
    print()
    print("=" * 78)
    print("C5  AGE ALONE IS NEVER SUFFICIENT")
    print("=" * 78)
    # The unmanipulated witness: the REAL machine lock, if a live suite holds it.
    # Read-only - `holder_state` stats and parses, and writes nothing.
    real = suitelock.path()
    holder = suitelock.read(real)
    if holder:
        age = (time.time() - os.path.getmtime(real)) / 60.0
        state, reason = suitelock.holder_state(real, holder)
        print("\n       the REAL machine lock, read-only, as it stands now:")
        print("       pid=%s branch=%r worktree=%r"
              % (holder.get("pid"), holder.get("branch"),
                 os.path.basename(str(holder.get("worktree")))))
        print("       started_at=%s  age=%.1f minutes  identity=%r"
              % (holder.get("started_at"), age, holder.get("identity")))
        print("       FIXED reader: %s (%s)" % (state, reason))
        print("       -> a %.0f-minute-old lock with a live holder is NOT taken."
              % age)
    else:
        print("\n       the real machine lock is not held at the moment, so the"
              "\n       fixture below is the only witness available.")

    # And the fixture: a live holder advertising a 150-minute hold. Only the two
    # DISPLAY strings are rewritten; the file mtime is restored, so the holder's
    # creation still correctly precedes its own lock write.
    directory = lockdir()
    os.makedirs(directory, exist_ok=True)
    file_path = os.path.join(directory, "suite.lock")
    child = spawn_child(file_path, "a-150-minute-suite", "120")
    try:
        child.stdout.readline()
        written = os.path.getmtime(file_path)
        payload = json.load(open(file_path, encoding="utf-8"))
        long_ago = time.strftime("%Y-%m-%dT%H:%M:%S",
                                 time.localtime(time.time() - 150 * 60))
        payload["queued_at"] = long_ago
        payload["started_at"] = long_ago
        with open(file_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle)
        os.utime(file_path, (written, written))
        print("\n       a FIXTURE lock advertising a 150-minute hold, held by a"
              " live pid %s" % payload.get("pid"))
        print("       started_at=%s" % long_ago)
        return verdicts(before, file_path, "c5")
    finally:
        child.kill()
        child.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", required=True,
                        help="path to the pre-fix src/suitelock.py, e.g. from "
                             "`git show 12de2433e`")
    args = parser.parse_args()
    before = load_before(args.before)
    print("CURRENT reader: %s" % args.before)
    print("FIXED   reader: %s" % suitelock.__file__)
    print("machine lock  : %s" % suitelock.path())
    print()
    c1_recycled_pid_is_reachable(before)
    c2_a_live_holder_is_respected(before)
    c3_died_at_start_is_reachable(before)
    c4_unobtainable_identity_waits(before)
    c5_age_alone_is_never_sufficient(before)
    print()
    print("=" * 78)
    print("done. no machine-wide lock was taken, created, modified or deleted.")


if __name__ == "__main__":
    raise SystemExit(main())
