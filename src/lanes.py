#!/usr/bin/env python3
"""Are the lane workers working? Read from files, and from nothing else.

WHY THIS MODULE EXISTS, and it is a measured gap rather than a feature idea.
On 2026-10-15 the operator asked four times whether the lanes were running,
and every honest answer needed a shell, because each of the three obvious
authorities is wrong in a different direction:

    a lane's `task-<lane>-<stamp>.out`   0 bytes until the task ENDS, so a
                                        working lane looks dead
    `queue/<lane>/DONE/`                 holds a file nobody's watcher named
                                        and misses tasks that finished, so
                                        its count is wrong in BOTH directions
    `queue/<lane>/` listed alone         says nothing about what is in flight

The one authority that answers is the watcher's own log line, and the only
live signal is the CPU time of the process under the watcher, read twice.
This module reads exactly those, and it is deliberately the ONLY thing in
this repository that knows the lane estate exists.

WHAT IT WILL NOT DO. It writes nothing - no state file, no cache file, no
ledger row. The CPU samples it needs in order to produce a delta live in
memory for the life of the process and are gone when it exits; a first read
therefore has no delta and says so rather than inventing one. It reaches no
provider, opens no socket and reads no credential. It needs no cooperation
from any lane: nothing has to be installed, no format has to change, and a
lane that is mid-task is not disturbed by being looked at.

THE RULE IT IS BUILT AROUND. An absence is reported as an absence. A log that
cannot be read makes a lane UNKNOWN, and UNKNOWN is never idle, never zero
and never ok - which is this estate's invariant 0, and the defect that has
cost it three findings in one day. Every function here returns `None` rather
than a plausible number when it cannot measure one.

TWO AUTHORITIES, CROSSED, NEVER COLLAPSED. The log says whether a task was
started and not finished. The process table says whether anything is alive
under that lane's watcher. They can disagree, and each disagreement is a real
condition with a real cause - a task that died without a DONE line, or an
orphan still running after one - so the four combinations are four answers
and not one traffic light.

    py -3 -m src.lanes
"""
import datetime
import os
import re

#: Where the lane estate lives. An environment variable rather than a constant
#: because the only real value names a person's home directory, and a path in
#: a tracked file is that person's name in a tracked file. Unset is its own
#: state: UNCONFIGURED, which is not "no lanes" and not "all idle".
OPS_DIR = "LANE_OPS_DIR"

# ------------------------------------------------------------------- states
#
# Each of these is a thing a reader must be able to tell apart from the
# others. Collapsing any pair of them is the defect this module exists for.

UNCONFIGURED = "unconfigured"    # nobody has said where the estate is
ABSENT = "absent"                # the path is not there
UNREADABLE = "unreadable"        # it is there and could not be read: UNKNOWN
EMPTY = "empty"                  # readable, and holds nothing
PRESENT = "present"              # readable, and holds something

RUNNING = "running"              # a START with no DONE after it
IDLE = "idle"                    # the newest record is a DONE
UNKNOWN = "unknown"              # the log could not be read at all
NEVER_RAN = "never_ran"          # the log is readable and names no task

# ------------------------------------------------------------- the verdicts
#
# THE VERDICT IS THE TWO AUTHORITIES CROSSED, and it exists because each one
# alone reads as healthy in a state the other calls broken. The log answers
# "was a task started and not finished". The process table answers "is
# anything alive under this lane's watcher". Five answers, and not one of
# them is a traffic light:

V_RUNNING = "running"        # both agree: a task is open and work is alive
V_STALLED = "stalled"        # the log has an open task and NOTHING is alive
V_IDLE = "idle"              # both agree: nothing open, nothing alive
V_ORPHANED = "orphaned"      # nothing open, and something is still alive
V_NEVER_RAN = "never_ran"    # a readable log that names no task at all
V_UNCROSSED = "uncrossed"    # the log answered and the table did not
V_UNKNOWN = "unknown"        # the log could not be read: no answer at all

# TWO VERDICTS ADDED 2026-10-16, and the first of them is a correction rather
# than a feature. Both were previously reported as V_RUNNING, which is the
# most misleading answer either one could have been given.
V_STUCK = "stuck"            # the refusal loop: the log moves, nothing works
V_DOWN = "down"              # the watcher itself has stopped

#: What each verdict means, and what it does NOT license. `running` is the
#: only one that means the lane is working, and even it says nothing about
#: whether the work is any good.
VERDICT_TEXT = {
    V_RUNNING: ("RUNNING",
                "the watcher log has a START with no DONE after it, and at "
                "least one process is alive under this lane's watcher"),
    V_STALLED: ("STALLED",
                "the log has an open task and NOTHING is alive under this "
                "watcher. The task died without a DONE line, or the watcher "
                "itself is gone - and either way the brief stays in RUNNING, "
                "so this lane consumes no further work until a person moves "
                "it. This is not idle and it is not running"),
    V_IDLE: ("IDLE",
             "the newest record is a DONE and nothing is alive under this "
             "watcher. The lane is between tasks"),
    V_ORPHANED: ("ORPHANED PROCESS",
                 "no task is open and something is still alive under this "
                 "watcher. An orphan surviving its task is a measured "
                 "failure in this estate: while it lives it can hold the "
                 "suite lock and the brief's file handle"),
    V_NEVER_RAN: ("NEVER RAN",
                  "the log is readable and contains no START for this lane. "
                  "No task has been dispatched here"),
    V_UNCROSSED: ("UNCROSSED",
                  "the log answered and the process table could not be "
                  "read, so one of the two authorities is missing. The log's "
                  "own answer is shown beside this and must not be read as "
                  "a verdict"),
    V_UNKNOWN: ("UNKNOWN",
                "this lane's watcher log is absent or unreadable. Nothing "
                "can be said about it - and UNKNOWN is not idle, not zero "
                "and not ok"),
    V_STUCK: ("STUCK",
              "the watcher is alive and REFUSING to start anything, because "
              "a brief is in RUNNING whose task owner is gone. It writes "
              "'a task is already in RUNNING' every 20 seconds, so the log "
              "is MOVING and every freshness check calls this lane healthy - "
              "and until a person clears RUNNING by hand this lane consumes "
              "no work at all. 7.66 lane-hours in 23 hours went here, and "
              "before 2026-10-16 this read as RUNNING"),
    V_DOWN: ("WATCHER DOWN",
             "the watcher itself has stopped - its log's last record is "
             "'watcher down', or the log has not moved and no watcher pid is "
             "live. Nothing will be dispatched here however deep the queue "
             "is, and this is NOT idle: idle means waiting for work, this "
             "means waiting for a person"),
}

#: The suffix the watcher appends to a DONE line, and what each one means.
#: Three of them are NOT the same answer and the board must not flatten them.
#: `exit0` is the only one the watcher treats as a completion, and even that
#: one proves the process exited and the lane file grew - never that the work
#: is right.
DONE_MEANINGS = {
    "exit0": ("completed",
              "the task process exited 0 and LANE-<lane>.md grew. That is "
              "the watcher's whole test; it is not evidence the work is "
              "correct"),
    "NOWORK": ("no work recorded",
               "exit 0 and the lane file did NOT grow, so the watcher "
               "counts it a failure. A model that wrote a plan instead of "
               "doing the work lands here"),
    "TIMEOUT": ("killed at the cap",
                "the task was still running at the timeout and its process "
                "tree was killed. Measured history says such a task was "
                "usually working, not hung - the work is unfinished rather "
                "than absent"),
}

#: Lines a lane writes when a gate it owed was not obtained. There is no
#: machine-readable field for this anywhere, so these are phrases - and a
#: phrase detector cannot read prose. It reports the LINE IT MATCHED and
#: never decides what the sentence meant: on tonight's corpus the second
#: pattern matches "Nothing else is owed", which is the opposite claim.
#:
#: WHAT WAS MEASURED, stated exactly, because a looser version of this note
#: was wrong. A plain substring test for "owed" matches "swallowed",
#: "followed" and "allowed" - that is what made a real lane file report a
#: marker it does not carry. The two word boundaries below are NOT what
#: prevents that; the verb requirement is, and either boundary could be
#: removed with the "swallowed" line still clean. Each boundary earns its
#: place on a different phrase, and a mutation watches each:
#:
#:     LEADING    "this owed reference" contains "is owed", so a passing
#:                mention matches without it
#:     TRAILING   "is owed_by_nobody" - an underscore is a word character,
#:                so `owed\b` rejects an identifier and a bare `owed` does
#:                not, and these files quote snake_case names in prose
#:                constantly
OWED_MARKERS = (
    ("not-obtained", re.compile(r"NOT\s+OBTAINED")),
    ("declared-owed",
     re.compile(r"(?i)\b(?:is|are|was|were|still|remains?)\s+"
                r"(?:still\s+)?OWED\b")),
)

#: The watcher's own line shape: `[2026-10-15 23:04:00] [webapp] START x.md`.
#: The lane tag is checked against the lane being read, because the watcher
#: appends each task's entire stdout into this same file with no delimiter,
#: and task prose is therefore interleaved with watcher records.
_LINE = re.compile(r"^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\] "
                   r"\[([^\]]+)\] (.*)$")
_START = re.compile(r"^START (.+)$")
_DONE = re.compile(r"^DONE\s+(.*?) -> (\S+)\s*$")

#: THE REFUSAL LOOP, and it is the most expensive state in this estate: 7.66
#: lane-hours in 23 hours, and nothing measured it. A watcher whose task
#: owner has died keeps writing this line every 20 seconds, so the log is
#: MOVING and anything that checks "has this log changed recently" calls the
#: lane healthy. 139 of these across five lanes in one day.
#:
#: It is not a `REFUSING:` line - those are about a duplicate watcher and a
#: missing tree-kill module - so the parser below did not recognise it at
#: all, and the board read the stale `START` with no `DONE` as RUNNING.
_BLOCKED = re.compile(r"^a task is already in RUNNING: (.+?), "
                      r"not starting another\s*$")

#: The lane's own timeout, from its own `watcher up` line. THE AUTHORITY IS
#: THE LOG AND NOT THE SCRIPT ON DISK: PowerShell parses a `-File` script
#: once, at load, so a running watcher keeps whatever constant it started
#: with. `queue/README.md` records the constant moving to 150m on 2026-10-15
#: 22:20 while five of the seven watchers were still running 90m.
_UP = re.compile(r"^watcher up\.(?:.*?\btimeout=(\d+)m)?")

#: The watcher stamps local time with no zone, so an age is computed against
#: local now. Comparing these to UTC would be silently wrong by the offset.
_STAMP = "%Y-%m-%d %H:%M:%S"

#: Only the tail of a log is read. A lane log is tens of kilobytes today and
#: grows with every task's stdout; an unbounded read on a page request is a
#: way to make a dashboard the slowest thing on the machine. If no record is
#: found inside the window the answer is UNKNOWN - never idle.
MAX_LOG_BYTES = 2 * 1024 * 1024

#: Guards on the descendant walk. A parent-pid table can contain a cycle
#: after pid reuse, and a walk that trusts it hangs.
MAX_WALK = 2000

#: Images that are part of a console process and never part of a task.
#:
#: MEASURED 2026-10-15 23:36 ACROSS ALL FIVE LIVE WATCHERS, and it is the one
#: defect that would have made this whole page lie. `conhost.exe` is the
#: Windows console host and is a PERMANENT child of every `powershell.exe`
#: watcher - it was the ONLY descendant of the one lane that was between
#: tasks. Counting it meant `count > 0` for every live watcher, so IDLE was
#: UNREACHABLE and an idle lane read ORPHANED PROCESS. The verdict was about
#: to be written into a lane file as a finding about another lane.
#:
#: A DENYLIST RATHER THAN AN ALLOWLIST, and the direction is the argument.
#: The precise rule would be "count only what sits under the watcher's
#: `cmd.exe` child", which is how `lane_watcher.ps1` launches a task - but if
#: that launch ever changed, such a reader would see nothing and report IDLE,
#: which is the dangerous answer. Excluding a known console host can only
#: ever remove a non-task process, so its failure mode is an under-count,
#: which pushes toward STALLED. An alarm that is wrong gets investigated; an
#: all-clear that is wrong does not.
IGNORED_IMAGES = ("conhost.exe",)

#: How often an IDLE watcher is documented to write a line.
#: `lane_watcher.ps1`: "One line every five minutes makes the log the single
#: authority for 'is this lane consuming work'". So an idle lane that has
#: said nothing for much longer than this is a lane whose single authority
#: has stopped answering - which is a different fact from a dead process and
#: is only asked while the log says idle, because a watcher mid-task is
#: legitimately quiet for as long as its task runs.
IDLE_HEARTBEAT_SECONDS = 300


def ops_root():
    """The lane estate's directory, or None when nobody has said where it is.

    Blank counts as unset. A variable set to the empty string is somebody
    having cleared it, not somebody having pointed it at the root of the
    filesystem.
    """
    value = (os.environ.get(OPS_DIR) or "").strip()
    return os.path.abspath(value) if value else None


# ------------------------------------------------- the one non-file authority
#
# Everything else here reads a file. This does not, and it is the only part
# that does not, so it is behind one seam with one refusal contract: every
# method answers `None` for "I could not measure that", and `None` is
# rendered as UNKNOWN rather than as a zero.
#
# It is a seam rather than a direct call for two reasons. A test must be able
# to present a process table without starting processes, and a platform this
# has no reader for must degrade to UNKNOWN rather than to an exception on a
# page request.


class SystemProbe:
    """pid -> parent pid, and a pid's CPU seconds. Never a command line.

    A command line on this machine carries file paths, and a credential has
    been passed on one before. This reads the parent pid, the image name and
    the accumulated CPU time, and the image name never leaves this class -
    the board gets a boolean from it and nothing more.
    """

    def table(self):
        """`{pid: (ppid, image_name)}`, or None when it cannot be read.

        None is UNKNOWN. An empty dict would say "this machine is running no
        processes", which is never true and would make every lane read as
        dead.
        """
        if os.name == "nt":
            return _nt_table()
        return _posix_table()

    def cpu(self, pid):
        """Accumulated kernel+user CPU seconds for `pid`, or None."""
        if os.name == "nt":
            return _nt_cpu(pid)
        return _posix_cpu(pid)


def _nt_table():
    """Toolhelp, through ctypes. No subprocess, so no shell and no timeout.

    `tasklist` is the other candidate and is what `suitelock` uses. It cannot
    serve here: it reports no parent pid and no CPU time, and it costs a
    process launch per call on a page request.
    """
    try:
        import ctypes
        from ctypes import wintypes
    except Exception:                                          # noqa: BLE001
        return None

    class ENTRY(ctypes.Structure):
        _fields_ = [("dwSize", wintypes.DWORD),
                    ("cntUsage", wintypes.DWORD),
                    ("th32ProcessID", wintypes.DWORD),
                    ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
                    ("th32ModuleID", wintypes.DWORD),
                    ("cntThreads", wintypes.DWORD),
                    ("th32ParentProcessID", wintypes.DWORD),
                    ("pcPriClassBase", ctypes.c_long),
                    ("dwFlags", wintypes.DWORD),
                    ("szExeFile", ctypes.c_char * 260)]

    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        snap = kernel32.CreateToolhelp32Snapshot(0x00000002, 0)
        if snap in (0, -1, 0xFFFFFFFF):
            return None
        try:
            entry = ENTRY()
            entry.dwSize = ctypes.sizeof(ENTRY)
            if not kernel32.Process32First(snap, ctypes.byref(entry)):
                return None
            table = {}
            while True:
                name = bytes(entry.szExeFile).split(b"\0")[0]
                table[int(entry.th32ProcessID)] = (
                    int(entry.th32ParentProcessID),
                    name.decode("latin-1", "replace"))
                if not kernel32.Process32Next(snap, ctypes.byref(entry)):
                    break
            return table or None
        finally:
            kernel32.CloseHandle(snap)
    except Exception:                                          # noqa: BLE001
        # UNKNOWN. A page that raised here would be a page that goes blank
        # because a process exited between two Windows calls.
        return None


def _nt_cpu(pid):
    """GetProcessTimes on a query-limited handle. None on any refusal."""
    try:
        import ctypes
        from ctypes import wintypes
    except Exception:                                          # noqa: BLE001
        return None
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        # PROCESS_QUERY_LIMITED_INFORMATION. The narrowest right that answers
        # this question: it cannot read memory and cannot signal the process.
        handle = kernel32.OpenProcess(0x1000, False, int(pid))
        if not handle:
            return None
        try:
            creation = wintypes.FILETIME()
            exited = wintypes.FILETIME()
            kernel = wintypes.FILETIME()
            user = wintypes.FILETIME()
            ok = kernel32.GetProcessTimes(handle, ctypes.byref(creation),
                                          ctypes.byref(exited),
                                          ctypes.byref(kernel),
                                          ctypes.byref(user))
            if not ok:
                return None
            total = 0
            for part in (kernel, user):
                total += (part.dwHighDateTime << 32) | part.dwLowDateTime
            # FILETIME counts 100-nanosecond intervals.
            return total / 1e7
        finally:
            kernel32.CloseHandle(handle)
    except Exception:                                          # noqa: BLE001
        return None


def _posix_table():
    """`/proc`, where there is one. None where there is not."""
    if not os.path.isdir("/proc"):
        return None
    table = {}
    try:
        names = os.listdir("/proc")
    except OSError:
        return None
    for name in names:
        if not name.isdigit():
            continue
        fields = _posix_stat(int(name))
        if fields is None:
            continue
        try:
            table[int(name)] = (int(fields[3]), fields[1].strip("()"))
        except (IndexError, ValueError):
            continue
    return table or None


def _posix_stat(pid):
    try:
        with open("/proc/%d/stat" % int(pid), encoding="utf-8") as handle:
            return handle.read().split()
    except (OSError, ValueError):
        return None


def _posix_cpu(pid):
    fields = _posix_stat(pid)
    if fields is None:
        return None
    try:
        ticks = os.sysconf("SC_CLK_TCK") or 100
        return (int(fields[13]) + int(fields[14])) / float(ticks)
    except (IndexError, ValueError, OSError, ZeroDivisionError):
        return None


def descendants(table, root, limit=MAX_WALK, ignore=IGNORED_IMAGES):
    """Every pid under `root`, excluding `root` itself. Bounded.

    `ignore` drops console-host processes from the RESULT while still walking
    THROUGH them, because not walking through them would be a second
    assumption about a tree this only measures. See `IGNORED_IMAGES` for why
    this exclusion exists and why it is a denylist.

    THE ROOT IS EXCLUDED DELIBERATELY. The watcher is a polling loop that
    accrues CPU time forever, so a sum that included it would show an idle
    lane burning cycles and the number would mean nothing.

    AN UPPER BOUND, NOT A PROOF. Windows reuses a pid, and a process whose
    real parent has exited keeps a parent pid that may now name something
    else entirely, so a parent-pid table cannot establish lineage. The
    watcher's own kill has the same limitation and documents it. This is
    therefore "pids that currently claim descent from the watcher", which is
    the honest reading and is what the board says it is.
    """
    children = {}
    for pid, (ppid, _name) in table.items():
        children.setdefault(ppid, []).append(pid)
    skip = tuple(name.lower() for name in (ignore or ()))
    found, frontier, seen = [], list(children.get(int(root), [])), {int(root)}
    while frontier and len(found) < limit:
        pid = frontier.pop()
        if pid in seen:
            continue
        seen.add(pid)
        image = ((table.get(pid) or (None, ""))[1] or "").lower()
        if image not in skip:
            found.append(pid)
        frontier.extend(children.get(pid, []))
    return sorted(found)


# ------------------------------------------------------------ the file reads


def _read_tail(path):
    """`(state, lines, truncated)`. Four states, and three of them are not rows.

    A missing file and an empty file are different facts about a lane, and an
    unreadable one is neither: it is the absence of the authority, which is
    strictly less than an empty authority.
    """
    if not os.path.exists(path):
        return ABSENT, [], False
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as handle:
            truncated = size > MAX_LOG_BYTES
            if truncated:
                handle.seek(size - MAX_LOG_BYTES)
            blob = handle.read()
    except OSError:
        return UNREADABLE, [], False
    text = blob.decode("utf-8", "replace")
    # MEASURED 2026-10-15: all seven real logs begin with a UTF-8 BOM,
    # because `Add-Content -Encoding UTF8` under Windows PowerShell 5.1
    # writes one. It sits in front of the FIRST record's `[`, so the anchored
    # parser below silently skipped the first line of every log. Today that
    # line is a configuration notice and nothing was lost; after a rotation
    # it would be a START, and a lane with one record would have read as
    # NEVER RAN.
    if text.startswith("﻿"):
        text = text[1:]
    lines = text.splitlines()
    if truncated and lines:
        # The seek landed mid-line. A partial line is dropped rather than
        # parsed, because half a timestamp is not a record.
        lines = lines[1:]
    if not lines:
        return EMPTY, [], truncated
    return PRESENT, lines, truncated


def watcher_events(lines, lane):
    """The watcher's own records, in order, from a log it shares with prose.

    THE SHARED FILE IS THE HARD PART AND IT IS NOT FULLY SOLUBLE. After each
    task the watcher appends that task's entire stdout into this same log
    with no delimiter, so model prose sits between watcher records. Anchoring
    on the full `[stamp] [lane] ` prefix AND on the lane tag matching removes
    all of it in tonight's corpus - but a task that printed a line of exactly
    that shape would be indistinguishable from a watcher record, and nothing
    in the format can tell them apart. The board states this rather than
    implying the log is machine-readable.
    """
    events = []
    for line in lines:
        match = _LINE.match(line)
        if not match or match.group(2) != lane:
            continue
        stamp, _tag, message = match.groups()
        when = _parse_stamp(stamp)
        start = _START.match(message)
        if start:
            events.append({"kind": "start", "at": stamp, "when": when,
                           "task": start.group(1).strip(), "line": line})
            continue
        done = _DONE.match(message)
        if done:
            events.append({"kind": "done", "at": stamp, "when": when,
                           "task": done.group(1).strip(),
                           "suffix": done.group(2), "line": line})
            continue
        blocked = _BLOCKED.match(message)
        if blocked:
            events.append({"kind": "blocked", "at": stamp, "when": when,
                           "task": blocked.group(1).strip(), "line": line})
            continue
        up = _UP.match(message)
        if up:
            events.append({"kind": "up", "at": stamp, "when": when,
                           # None when the line carries no `timeout=` field.
                           # Not a default: a timeout nobody stated is
                           # UNKNOWN, and guessing it would make every
                           # STUCK verdict a guess too.
                           "timeout_minutes": (int(up.group(1))
                                               if up.group(1) else None),
                           "line": line})
            continue
        if message.startswith("TIMEOUT after "):
            events.append({"kind": "timeout_notice", "at": stamp,
                           "when": when, "line": line})
        elif message.startswith("watcher down"):
            events.append({"kind": "down", "at": stamp, "when": when,
                           "line": line})
        elif message.startswith("REFUSING:"):
            events.append({"kind": "refused", "at": stamp, "when": when,
                           "line": line})
        elif message.startswith("idle: "):
            events.append({"kind": "idle", "at": stamp, "when": when,
                           "line": line})
    return events


def _parse_stamp(stamp):
    """A naive local datetime, or None. Never a guess at a timezone.

    The watcher writes `Get-Date -Format "yyyy-MM-dd HH:mm:ss"`, which
    carries no offset. Treating it as UTC would be wrong by the machine's
    offset all day and the error would look like a plausible duration.
    """
    try:
        return datetime.datetime.strptime(stamp, _STAMP)
    except (TypeError, ValueError):
        return None


def _seconds_between(earlier, later):
    if earlier is None or later is None:
        return None
    return int((later - earlier).total_seconds())


def _list_md(path):
    """`(state, names)` for the briefs in a directory, watcher-ordered.

    `*.md` and nothing else, including names beginning with an underscore,
    because that is exactly what `Get-ChildItem -Filter *.md` gives the
    watcher. Ordered case-insensitively, the way `Sort-Object Name` does, so
    the name this reports as next is the one the watcher will take.
    """
    if not os.path.exists(path):
        return ABSENT, []
    if not os.path.isdir(path):
        # It is there and it is not a directory. That is UNREADABLE, never
        # ABSENT: the authority exists and its contents cannot be
        # established, which is strictly less information than its not being
        # there at all. Reporting it ABSENT was this reader's own first
        # version of the defect the whole page exists to prevent.
        return UNREADABLE, []
    try:
        names = [n for n in os.listdir(path) if n.lower().endswith(".md")
                 and os.path.isfile(os.path.join(path, n))]
    except OSError:
        return UNREADABLE, []
    return PRESENT, sorted(names, key=lambda n: n.lower())


def _read_pid_file(path):
    """`(state, pid)`. A file whose contents are not a pid is UNREADABLE.

    The watcher removes this on a clean exit, so ABSENT means no watcher is
    registered - which is not the same as no watcher running, because a hard
    kill leaves the file behind with a dead pid in it.
    """
    if not os.path.exists(path):
        return ABSENT, None
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            raw = handle.read().strip()
    except OSError:
        return UNREADABLE, None
    if not raw:
        return EMPTY, None
    try:
        return PRESENT, int(raw)
    except ValueError:
        return UNREADABLE, None


def owed_markers(path):
    """What a lane's own file says about a gate it has not obtained.

    THE SCOPE IS A HEURISTIC AND IS REPORTED AS ONE. A lane file has no
    machine-readable entry boundary: most lanes open an entry with a dated
    `## ` heading, and at least one writes several `## ` headings inside one
    entry, so the last `## ` can be NARROWER than the last entry. The
    returned dict therefore names the heading and its line number and says
    whether it is dated, and it counts the markers that fall OUTSIDE the
    scope rather than hiding them.

    NO MARKER IS NOT "NOTHING IS OWED". A lane that phrased it some other way
    is not detected, and the page is required to say that where it shows
    this.
    """
    if not os.path.exists(path):
        return {"state": ABSENT, "hits": [], "before": 0, "heading": None,
                "heading_line": None, "heading_dated": None}
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            lines = handle.read().splitlines()
    except OSError:
        return {"state": UNREADABLE, "hits": [], "before": 0, "heading": None,
                "heading_line": None, "heading_dated": None}
    headings = [i for i, line in enumerate(lines) if line.startswith("## ")]
    start = headings[-1] if headings else 0
    heading = lines[start] if headings else None
    hits, before = [], 0
    for index, line in enumerate(lines):
        for name, pattern in OWED_MARKERS:
            if not pattern.search(line):
                continue
            if index >= start:
                hits.append({"line": index + 1, "marker": name,
                             "text": line.strip()})
            else:
                before += 1
            break
    return {
        "state": PRESENT,
        "hits": hits,
        "before": before,
        "heading": heading,
        "heading_line": (start + 1) if headings else None,
        # A dated heading is very likely one entry; an undated one is very
        # likely a sub-part of an entry, which makes the scope too narrow.
        "heading_dated": bool(
            headings and re.match(r"^##\s+\d{4}-\d{2}-\d{2}", heading)),
    }


# ------------------------------------------------------------------ the board



# ------------------------------------------------- starvation and the floor
#
# WHY THIS LAYER EXISTS, measured over 2026-10-15 01:30 -> 2026-10-16 00:45:
# the seven lanes did 38.8 lane-hours of work in ~137 lane-hours of wall
# clock, 28% utilisation, and 89.9 of the 94.3 lane-hours lost to gaps were
# an EMPTY QUEUE rather than a broken lane. The `0040` board answers "what is
# this lane doing". It cannot answer "which lane is about to run out of work,
# and when", and that is the question that cost the most.
#
# Everything here is derived from the watcher log and the queue directory.
# Nothing is derived from the three signals `0040` already measured wrong,
# and each rejection is restated at its use site rather than left in a
# docstring somebody has to find.

#: Never below this many queued briefs. The floor is the operator's, written
#: in `queue/README.md`. A floor nobody can see is not a floor, which is the
#: whole reason this module grew these functions.
FLOOR = 3

#: How far back utilisation is computed. A day, because the measurement that
#: produced the floor was over a day and a shorter window makes a lane that
#: has just finished a long task look fully utilised.
UTILISATION_WINDOW_SECONDS = 24 * 3600


def task_durations(events):
    """Minutes for every START that has a matching DONE, oldest first.

    PAIRED BY TASK NAME AND NOT BY POSITION. A lane that was killed mid-task
    leaves a START with no DONE, and pairing positionally would then measure
    the gap from that orphan to the NEXT task's completion - which is not a
    duration, it is two tasks plus a gap, and it would inflate the median
    that the starvation estimate rests on.
    """
    open_starts = {}
    out = []
    for event in events:
        if event["kind"] == "start":
            open_starts[event["task"]] = event
        elif event["kind"] == "done":
            start = open_starts.pop(event["task"], None)
            if start is None:
                continue
            seconds = _seconds_between(start["when"], event["when"])
            # A DONE stamped before its own START is a real artifact here:
            # lanes write their own DONE files and `Move-Item` preserves the
            # original mtime. Dropped rather than counted as a negative
            # duration, and the count of dropped pairs is reported.
            if seconds is not None and seconds >= 0:
                out.append(seconds / 60.0)
    return out


def median_minutes(events):
    """This lane's own median task duration, or None.

    ITS OWN, not the estate's. glm's median is 28 minutes and glm-b's is 16,
    and the difference decides who starves first - an estate median would
    put both at the same risk and be wrong about both.
    """
    durations = sorted(task_durations(events))
    if not durations:
        return None
    middle = len(durations) // 2
    if len(durations) % 2:
        return durations[middle]
    return (durations[middle - 1] + durations[middle]) / 2.0


def timeout_minutes(events):
    """The timeout this lane is ACTUALLY running, from its own log.

    From the last `watcher up` line, because PowerShell parses a `-File`
    script once at load: a running watcher keeps whatever constant it
    started with, so the script on disk and `queue/README.md` are both
    wrong about a watcher that started before the constant changed. None
    when no `watcher up` line carries the field - never a default, because a
    guessed timeout would make every STUCK verdict a guess.
    """
    for event in reversed(events):
        if event["kind"] == "up" and event.get("timeout_minutes"):
            return event["timeout_minutes"]
    return None


def starvation(depth, median):
    """Minutes of autonomy left: depth x this lane's own median.

    None when either input is unknown. A lane with no completed task has no
    median, and multiplying by a borrowed one would produce a confident
    number about a lane nothing is known about.
    """
    if depth is None or median is None:
        return None
    return depth * median


def utilisation(events, now, window=UTILISATION_WINDOW_SECONDS):
    """Busy minutes over wall minutes in the window, from the log alone.

    BUSY IS A PAIRED START..DONE INTERVAL, clipped to the window. An open
    START is counted up to `now`, because a task running right now is busy -
    but a STUCK lane's open START is NOT busy, and this function cannot tell
    those apart, so `board` reports utilisation beside the verdict rather
    than instead of it. Stated here because a single number that silently
    counts dead time as work is how 28% looked like 88%.
    """
    if now is None:
        return None
    floor_time = now - datetime.timedelta(seconds=window)
    busy = 0
    open_starts = {}
    for event in events:
        if event["kind"] == "start":
            open_starts[event["task"]] = event
        elif event["kind"] == "done":
            start = open_starts.pop(event["task"], None)
            if start is None or start["when"] is None \
                    or event["when"] is None:
                continue
            busy += _overlap(start["when"], event["when"], floor_time, now)
    for start in open_starts.values():
        if start["when"] is not None:
            busy += _overlap(start["when"], now, floor_time, now)
    wall = (now - max(floor_time, _first_when(events) or floor_time))
    wall_seconds = int(wall.total_seconds())
    if wall_seconds <= 0:
        return None
    return {"busy_seconds": busy, "wall_seconds": wall_seconds,
            "percent": round(100.0 * busy / wall_seconds, 1)}


def _overlap(start, end, floor_time, ceiling):
    """Seconds of [start, end] inside [floor_time, ceiling]. Never negative."""
    low = max(start, floor_time)
    high = min(end, ceiling)
    if high <= low:
        return 0
    return int((high - low).total_seconds())


def _first_when(events):
    for event in events:
        if event["when"] is not None:
            return event["when"]
    return None


def stuck_run(events):
    """The refusal loop, or None. THE MOST EXPENSIVE STATE IN THE ESTATE.

    A watcher whose task owner has died writes `a task is already in
    RUNNING: <brief>, not starting another` every 20 seconds. The log is
    MOVING, so every freshness check calls the lane healthy, and `0040`'s
    board reads the stale START with no DONE as RUNNING. 7.66 lane-hours in
    23 hours, and no instrument showed it.

    Returns the run of consecutive `blocked` events naming ONE brief with no
    intervening START or DONE, with the moment the stuck task began - which
    is the last START before the run when there is one, because that is when
    the work actually started, and the first refusal otherwise.
    """
    run = []
    brief = None
    began = None
    last_start = None
    for event in events:
        if event["kind"] in ("start", "done"):
            # A START or a DONE ends any run: the lane moved.
            run = []
            brief = None
            began = None
            if event["kind"] == "start":
                last_start = event
            else:
                last_start = None
            continue
        if event["kind"] != "blocked":
            continue
        if brief is not None and event["task"] != brief:
            # A different brief is a different refusal loop, not a longer
            # one. Counting them together would overstate the elapsed time.
            run = []
            began = None
        brief = event["task"]
        run.append(event)
        if began is None:
            began = (last_start or event)
    if not run:
        return None
    return {"task": brief, "count": len(run),
            "began_at": (began or {}).get("at"),
            "began_when": (began or {}).get("when"),
            "from_a_start": began is last_start and last_start is not None,
            "last_at": run[-1]["at"], "last_when": run[-1]["when"]}

def lane_names(root):
    """`[(name, where_it_was_found)]`, from both authorities, union.

    A lane with a queue folder and no log has never been started. A lane with
    a log and no queue folder had its folder removed, or was renamed. Both
    are worth seeing, and neither is discoverable from the other authority,
    so the set is the union and every row carries where it came from.

    Names beginning with `_` are skipped: the queue folder holds
    `_STANDING-RULES.md` at its top level and the convention is clear.
    """
    queue_root = os.path.join(root, "queue")
    log_root = os.path.join(root, "logs")
    found = {}
    try:
        for name in sorted(os.listdir(queue_root)):
            if name.startswith("_") or name.startswith("."):
                continue
            if os.path.isdir(os.path.join(queue_root, name)):
                found[name] = "queue"
    except OSError:
        pass
    try:
        for name in sorted(os.listdir(log_root)):
            match = re.match(r"^watcher-(.+)\.log$", name)
            if not match:
                continue
            lane = match.group(1)
            found[lane] = "both" if lane in found else "log"
    except OSError:
        pass
    return sorted(found.items())


def _cpu_reading(lane, root_pid, probe, table, now, samples):
    """The subtree's CPU seconds and the delta since the last look.

    FOUR DIFFERENT NOTHINGS, and a zero would be a lie in three of them:

        no table            the process table could not be read -> UNKNOWN
        no watcher pid      no file names a root to walk from   -> UNKNOWN
        no descendants      the table was read and nothing is under the
                            watcher. This one IS a measurement, and a 0 here
                            is a real zero rather than an absence
        no previous sample  the first look in this process. The delta is
                            UNKNOWN; a second look produces one

    The samples are held in memory, never written. That is a deliberate
    limitation: restarting the process loses them, and a reader who needs a
    delta loads the page twice - which is exactly the method the operator
    used by hand.
    """
    reading = {"root_pid": root_pid, "pids": None, "count": None,
               "seconds": None, "delta_seconds": None, "wall_seconds": None,
               "unmeasured": [], "why": None}
    if table is None:
        reading["why"] = ("the process table could not be read on this "
                          "platform, so liveness is UNKNOWN rather than idle")
        return reading
    if root_pid is None:
        reading["why"] = ("no file names this lane's watcher process, so "
                          "there is no root to walk from")
        return reading
    if root_pid not in table:
        reading["pids"], reading["count"], reading["seconds"] = [], 0, 0.0
        reading["why"] = ("the pid file names a process that is not in the "
                          "table. That watcher is gone, so this lane is "
                          "consuming nothing whatever its log last said")
        return reading

    pids = descendants(table, root_pid)
    total, unmeasured = 0.0, []
    for pid in pids:
        seconds = probe.cpu(pid)
        if seconds is None:
            # Counted, never treated as zero: a process this cannot open is
            # still a running process.
            unmeasured.append(pid)
            continue
        total += seconds
    reading["pids"] = pids
    reading["count"] = len(pids)
    reading["unmeasured"] = unmeasured
    reading["seconds"] = None if (pids and len(unmeasured) == len(pids)) \
        else round(total, 1)

    key = (lane, root_pid)
    previous = samples.get(key)
    if reading["seconds"] is not None:
        samples[key] = (now, reading["seconds"])
    if previous and reading["seconds"] is not None:
        then, before = previous
        delta = round(reading["seconds"] - before, 1)
        wall = _seconds_between(then, now)
        if delta < 0:
            # A subtree's accumulated CPU cannot fall. It did, so the pids
            # under this watcher are not the ones that were there before.
            reading["why"] = ("the CPU sample went backwards, so the "
                              "processes under this watcher are not the ones "
                              "the previous sample measured")
        elif not wall:
            # Two samples in the same second say nothing: a busy process can
            # accrue no measurable CPU in that window, so "+0.0s in 0s" would
            # read as a stall that was never observed. Found by this module's
            # own tests, where one process rendered the page twice.
            reading["why"] = ("the previous sample is from this same second, "
                              "so there is no window to measure across. "
                              "Load this page again in a moment")
        else:
            reading["delta_seconds"] = delta
            reading["wall_seconds"] = wall
    elif reading["seconds"] is not None:
        reading["why"] = ("first sample in this process - there is nothing "
                          "to compare it with. Load this page again for a "
                          "delta")
    return reading


#: CPU samples from the last look, in memory only, keyed by (lane, root pid).
#: Not a state file, deliberately: this module writes nothing, and a cache on
#: disk would be a second representation of a fact the process table owns.
_SAMPLES = {}


def board(root=None, now=None, probe=None, samples=None):
    """One row per lane, and every unanswerable question answered UNKNOWN.

    `root` defaults to `ops_root()`. When nothing has said where the estate
    is, the board is UNCONFIGURED and names the variable - which is not
    "there are no lanes" and must not render as a clean empty table.
    """
    now = now or datetime.datetime.now()
    probe = probe or SystemProbe()
    samples = _SAMPLES if samples is None else samples
    root = root or ops_root()

    if root is None:
        return {"state": UNCONFIGURED, "root": None, "variable": OPS_DIR,
                "lanes": [], "table_read": None, "at": now}
    if not os.path.isdir(root):
        return {"state": ABSENT, "root": root, "variable": OPS_DIR,
                "lanes": [], "table_read": None, "at": now}

    table = probe.table()
    rows = []
    for lane, where in lane_names(root):
        rows.append(_lane_row(root, lane, where, probe, table, now, samples))

    # Prune in-memory samples for lanes and pids that are no longer there, so
    # a long-lived process does not accumulate a row per dead watcher.
    live = {(r["lane"], r["cpu"]["root_pid"]) for r in rows}
    for key in [k for k in samples if k not in live]:
        samples.pop(key, None)

    return {
        "state": PRESENT,
        "root": root,
        "variable": OPS_DIR,
        "at": now,
        # None means the process table could not be read. Every liveness
        # answer on the board is UNKNOWN in that case, and the page says so
        # once at the top rather than seven times.
        "table_read": table is not None,
        "lanes": rows,
        # The operator's floor, travelling WITH the data so the renderer
        # holds no copy of it and the two cannot drift.
        "floor": FLOOR,
    }


def _lane_row(root, lane, where, probe, table, now, samples):
    log_path = os.path.join(root, "logs", "watcher-%s.log" % lane)
    pid_path = os.path.join(root, "logs", "watcher-%s.pid" % lane)
    queue_path = os.path.join(root, "queue", lane)
    running_path = os.path.join(queue_path, "RUNNING")
    lane_file = os.path.join(root, "LANE-%s.md" % lane)

    log_state, lines, truncated = _read_tail(log_path)
    events = watcher_events(lines, lane) if log_state == PRESENT else []

    starts = [e for e in events if e["kind"] == "start"]
    dones = [e for e in events if e["kind"] == "done"]
    last_start = starts[-1] if starts else None
    last_done = dones[-1] if dones else None
    last_event = events[-1] if events else None

    # THE STATUS COMES FROM ORDER, NOT FROM THE LAST LINE. A task's own stdout
    # is appended after its DONE line, and the watcher logs MOVED and idle
    # lines afterwards, so "the last line mentions DONE" is not the test. The
    # test is whether the newest START is newer than the newest DONE.
    if log_state in (ABSENT, UNREADABLE):
        status = UNKNOWN
    elif not starts:
        status = NEVER_RAN
    elif last_done is None:
        status = RUNNING
    else:
        running = events.index(last_start) > events.index(last_done)
        status = RUNNING if running else IDLE

    if status == RUNNING:
        since = _seconds_between(last_start["when"], now)
    elif status == IDLE and last_done is not None:
        since = _seconds_between(last_done["when"], now)
    else:
        since = None

    # HOW LONG SINCE THIS WATCHER SAID ANYTHING AT ALL, which is a different
    # question from whether its process exists. `lane_watcher.ps1` logs
    # `idle: queue empty` every five minutes precisely so that a log which
    # has stopped moving is distinguishable from a script that has died - and
    # its `Log` helper SWALLOWS a failed `Add-Content`, so lines can be lost
    # with no error anywhere.
    #
    # MEASURED 2026-10-15 23:40: one lane's watcher process was alive and had
    # written nothing for 19 minutes, with no MOVED line after its DONE and
    # not one idle heartbeat. Both authorities this page crosses said IDLE,
    # correctly - and neither could say that the lane had also gone quiet.
    silence = _seconds_between(last_event["when"], now) if last_event else None

    pid_state, root_pid = _read_pid_file(pid_path)
    cpu = _cpu_reading(lane, root_pid, probe, table, now, samples)

    # The watcher's own soundness check, reused rather than reinvented: it
    # refuses to treat a pid as a live watcher unless the image is a shell.
    # Only the verdict is kept - the image name never leaves here.
    # `pwsh` as well as `powershell`, because the watcher's own `-like
    # "*powershell*"` would call PowerShell 7 not a shell, and a false alarm
    # on a healthy lane is how a reader learns to stop reading the column.
    watcher_image_ok = None
    if table is not None and root_pid is not None:
        entry = table.get(root_pid)
        image = ((entry[1] if entry else None) or "").lower()
        watcher_image_ok = bool(entry) and ("powershell" in image
                                            or "pwsh" in image)

    queue_state, queued = _list_md(queue_path)
    running_state, inflight = _list_md(running_path)

    # TWO AUTHORITIES, CROSSED. Neither overrules the other: where they
    # disagree the verdict names the disagreement instead of picking a side,
    # and where one of them is missing the verdict says UNCROSSED rather than
    # reporting the surviving one as though it were both.
    # The starvation layer, and the two states it makes visible. Computed
    # before the verdict because two of them OUTRANK it.
    stuck = stuck_run(events)
    lane_timeout = timeout_minutes(events)
    median = median_minutes(events)
    depth = len(queued) if queue_state == PRESENT else None
    # The refusal loop is only STUCK once it is past THIS LANE's own timeout,
    # per the brief: before that the task may simply be long. An unknown
    # timeout therefore cannot produce a STUCK verdict - it is reported as a
    # refusal loop of unknown standing instead of a guess.
    stuck_seconds = (_seconds_between(stuck["began_when"], now)
                     if stuck else None)
    is_stuck = bool(stuck and lane_timeout is not None
                    and stuck_seconds is not None
                    and stuck_seconds > lane_timeout * 60)
    went_down = bool(last_event and last_event["kind"] == "down")

    if status == UNKNOWN:
        verdict = V_UNKNOWN
    elif is_stuck:
        # BEFORE the cross, because the cross gets this one wrong in the
        # worst direction: the log has an open START and the watcher process
        # IS alive, so both authorities agreed on RUNNING while the lane did
        # nothing for 97 minutes. Measured twice on 2026-10-15.
        verdict = V_STUCK
    elif went_down:
        # Also before the cross. A watcher that logged `watcher down` will
        # dispatch nothing however deep the queue is, and reporting that as
        # IDLE makes a dead lane look like it is merely between tasks.
        verdict = V_DOWN
    elif cpu["count"] is None:
        verdict = V_UNCROSSED
    elif status == RUNNING:
        verdict = V_RUNNING if cpu["count"] > 0 else V_STALLED
    elif status == NEVER_RAN:
        verdict = V_ORPHANED if cpu["count"] > 0 else V_NEVER_RAN
    else:
        verdict = V_ORPHANED if cpu["count"] > 0 else V_IDLE

    return {
        "lane": lane,
        "found_in": where,
        # The LOG's answer, on its own. Kept separately from the verdict so a
        # reader can see which authority said what.
        "status": status,
        "verdict": verdict,
        "since_seconds": since,
        # ----------------------------------------- starvation and the floor
        # `depth` is already below as `queue_depth`; these are the answers
        # built on it. Every one is None rather than 0 when it could not be
        # measured, because "no autonomy left" and "nobody knows how much
        # autonomy is left" are different alarms.
        "median_task_minutes": median,
        "starvation_minutes": starvation(depth, median),
        # The floor is the operator's, from `queue/README.md`. None when the
        # depth itself is unknown: an unreadable queue is not a breach and
        # is not compliance either.
        "below_floor": None if depth is None else depth < FLOOR,
        "floor": FLOOR,
        # From this lane's own `watcher up` line, NOT from the script on
        # disk - a running watcher keeps the constant it loaded with.
        "timeout_minutes": lane_timeout,
        "timeout_from": "this lane's own `watcher up` line",
        "utilisation": utilisation(events, now),
        # The refusal loop, shown whether or not it has passed the timeout:
        # a loop that has not yet is still the thing to watch, and hiding it
        # until it qualifies would hide the lead time.
        "refusal_loop": stuck,
        "refusal_loop_seconds": stuck_seconds,
        "is_stuck": is_stuck,
        # Why a refusal loop could NOT be ruled STUCK. Named rather than
        # silently treated as healthy.
        "stuck_undecidable": bool(stuck and lane_timeout is None),
        "watcher_went_down": went_down,
        # Is the process the pid file names in the table at all? None when
        # the table could not be read or no file names a pid. A dead watcher
        # is the root answer to "is this lane consuming work", and it is
        # invisible in the log: the log's last line looks the same either way.
        "watcher_alive": None if (table is None or root_pid is None)
                         else root_pid in table,
        # Verbatim, because the suffix is the part that is usually lost. The
        # page renders the line as it stands and never summarises it.
        "last_done_line": last_done["line"] if last_done else None,
        "last_done_task": last_done["task"] if last_done else None,
        "last_done_suffix": last_done["suffix"] if last_done else None,
        "last_done_at": last_done["at"] if last_done else None,
        "last_start_task": last_start["task"] if last_start else None,
        "last_start_at": last_start["at"] if last_start else None,
        "last_event_kind": last_event["kind"] if last_event else None,
        "last_event_at": last_event["at"] if last_event else None,
        # Seconds since this watcher's newest record, or None when it has
        # none. NOT a verdict: a watcher mid-task is legitimately quiet for
        # as long as the task runs. It is only a question worth asking when
        # the log says idle, because an idle watcher is documented to
        # heartbeat.
        "log_silent_seconds": silence,
        "heartbeat_seconds": IDLE_HEARTBEAT_SECONDS,
        "log_has_gone_quiet": bool(
            status == IDLE and silence is not None
            and silence > IDLE_HEARTBEAT_SECONDS * 2),
        "log_state": log_state,
        "log_truncated": truncated,
        "records": len(events),
        "watcher_pid_state": pid_state,
        "watcher_pid": root_pid,
        "watcher_image_ok": watcher_image_ok,
        "cpu": cpu,
        "queue_state": queue_state,
        "queue_depth": None if queue_state != PRESENT else len(queued),
        "next_up": queued[0] if queued else None,
        "running_state": running_state,
        "inflight": inflight,
        "owed": owed_markers(lane_file),
    }


def describe(data=None):
    """The board as text, for a terminal. Same reader, same refusals."""
    data = data or board()
    if data["state"] == UNCONFIGURED:
        return "UNCONFIGURED: set %s to the lane estate's directory." % \
            data["variable"]
    if data["state"] == ABSENT:
        return "ABSENT: %s names %s, which is not a directory." % \
            (data["variable"], data["root"])
    out = ["%s  (process table: %s)"
           % (data["root"],
              "read" if data["table_read"] else "UNREADABLE - liveness UNKNOWN")]
    for row in data["lanes"]:
        cpu = row["cpu"]
        out.append(
            "  %-12s %-9s %-9s %-6s depth=%-4s cpu=%-8s d=%-7s %s"
            % (row["lane"], VERDICT_TEXT[row["verdict"]][0].split()[0],
               "log:" + row["status"],
               "-" if row["since_seconds"] is None
               else "%dm" % (row["since_seconds"] // 60),
               "UNKNOWN" if row["queue_depth"] is None else row["queue_depth"],
               "UNKNOWN" if cpu["seconds"] is None else cpu["seconds"],
               "UNKNOWN" if cpu["delta_seconds"] is None
               else cpu["delta_seconds"],
               row["last_done_suffix"] or "-"))
        if row["verdict"] in (V_STALLED, V_ORPHANED):
            out.append("      " + VERDICT_TEXT[row["verdict"]][1])
        if row["log_has_gone_quiet"]:
            out.append("      THE LOG HAS GONE QUIET: nothing for %d minutes, "
                       "and an idle watcher logs every %d"
                       % (row["log_silent_seconds"] // 60,
                          row["heartbeat_seconds"] // 60))
        for hit in row["owed"]["hits"]:
            out.append("      OWED MARKER line %d: %s"
                       % (hit["line"], hit["text"][:90]))
    return "\n".join(out)


if __name__ == "__main__":                                  # pragma: no cover
    print(describe())
