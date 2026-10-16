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

from src import suitelock

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

# ------------------------------------------ the outcome of a CLOSED task
#
# WHY THIS LAYER EXISTS, and it is the most expensive misreport this estate
# has measured. Between 01:41 and 01:48 on 2026-10-16 the `glm`, `glm-b` and
# `glm-c` watchers consumed eight briefs in seven minutes and NOT ONE of
# those tasks ran. Every one was a provider refusal - the GLM plan's rolling
# five-hour usage window - and the watcher, having no verdict for NEVER
# STARTED, wrote the one it had:
#
#     [2026-10-16 01:41:36] [glm]   DONE  0067b-save-sweep.md -> exit1
#
# `exit1` means ran-and-failed, and a failure CONSUMES the brief: the watcher
# moves it into `DONE\` and takes the next file. The board read those lines
# and rendered three lanes that each failed three tasks. The truth is three
# lanes that each ran nothing and lost three briefs - two of them,
# `glm/0072` and `glm-c/0230`, on the canary critical path, and alive today
# only because a person copied them back out of `DONE\` by hand at 01:49.
# That is catalogue family 6 happening on the instrument itself: a result the
# instrument has no name for, reported as the nearest name it has.
#
# WHAT THE PREDICATE MAY NOT READ. All eight `.out` files are 713 bytes,
# which is how a person recognises this at a glance - and `CONTINUITY.md`
# trap 6 records the SAME refusal at 559 bytes, with the error line landing
# earlier. So the size goes in the display and never in the test, and
# neither does the exit code, the lane, the model, or three failures in a
# row. Content only.
#
# AND IT FAILS TOWARD "ORDINARY FAILURE", WHICH IS THE DIRECTION THAT COSTS
# LESS. A detector that fired on every exit1 would tell the operator to
# restore briefs that really did fail - worse than the label it replaces,
# because that one loses a brief while this one would lose the record of a
# real failure AND waste the re-run. So a refusal is claimed only where the
# output is a refusal line and NOTHING ELSE but the harness's own preamble. A
# refusal line sitting on top of real work is an ordinary failure with a flag
# on it, and the flag is shown.

O_REFUSED = "refused"   # the provider rejected the request: the task NEVER ran
O_FAILED = "failed"     # the `.out` holds the task's own output: it ran, badly
O_UNKNOWN = "unknown"   # absent, unreadable or empty: not classifiable at all

#: What each outcome means AND WHAT ACTION IT IMPLIES, which is the part the
#: watcher's two words could not carry. Deliberately kept apart from the lane
#: verdicts above: a lane whose task was refused is not a failing lane, and it
#: is not a DOWN lane either until its watcher actually exits. Those are three
#: different states needing three different things from a person.
OUTCOME_TEXT = {
    O_REFUSED: (
        "REFUSED",
        "the provider rejected this task's LAST request and the `.out` holds "
        "nothing else, so NO WORK IS RECORDED - and the watcher, having no "
        "word for that, recorded a task that ran and failed and CONSUMED THE "
        "BRIEF. WHETHER THE SESSION ACTED BEFORE THE REFUSAL IS A SEPARATE "
        "QUESTION, answered by `elapsed_seconds` beside this and by nothing "
        "in the output: `claude -p` emits its result when it ends, so a "
        "session cut off after 59 minutes leaves a file byte-for-byte "
        "identical to one refused at dispatch. The action is a person's: "
        "move the brief back out of the DONE folder into the lane queue. "
        "Nothing here moves it. This is NOT a failing lane and NOT a dead "
        "lane"),
    O_FAILED: (
        "FAILED",
        "the `.out` holds this task's own output, so the task ran and the "
        "watcher's verdict stands. The brief was consumed because it was "
        "attempted: it is NOT restored, and what it wrote is read by a "
        "person"),
    O_UNKNOWN: (
        "UNKNOWN",
        "the `.out` for this CLOSED task is absent, unreadable, or 0 bytes. "
        "A failure that cannot be read cannot be classified, so this is "
        "neither a refusal nor an ordinary failure - and 0 bytes is not an "
        "empty task: the file fills when the task ends, so for a closed task "
        "0 bytes means the output was lost"),
}

#: The provider's own refusal line, verbatim from all eight `.out` files:
#:
#:     API Error: Request rejected (429) . [1308][Usage limit reached for
#:     5 hour. Your limit will reset at 2026-10-16 08:07:16][2026100...]
#:
#: `Request rejected` is the provider saying it did not accept THE REQUEST
#: THIS LINE ANSWERS, which is what separates a refusal from a failure - and
#: NOT, as this comment said until 2026-10-16, what makes it a never-started
#: task. The provider declining a session's LAST request says nothing about
#: whether it accepted an earlier one in the same session, and three of the
#: eight refusals below ran 24.4, 59.1 and 59.3 minutes before this line
#: arrived. `elapsed_seconds` on each row is the figure that answers it.
#: THE STATUS CODE IS CAPTURED AND NOT TESTED: 429 is what was measured, and
#: a rejection carrying another code is still a rejection. The quota wording
#: is read for the reset time below and is NOT part of the test either - a
#: synonym nobody has seen is not evidence, and inventing one would widen the
#: predicate on a guess.
_REFUSAL = re.compile(r"^API Error:\s*Request rejected\s*\((\d{3})\)")

#: Lines the harness prints before a task has done anything. A refusal is
#: claimed only when every other line in the output is one of these, so this
#: tuple is what decides "nothing is RECORDED" - and it fails SAFE: a notice
#: nobody has listed here makes a real refusal read as an ordinary failure
#: WITH ITS REFUSAL LINE STILL SHOWN, rather than making an ordinary failure
#: read as a refusal.
#:
#: Both are measured, in all eight refusals and in the 709-byte near-miss
#: that is this detector's negative control - same lane, same two notices,
#: four bytes of difference, and a real task report instead of an error. The
#: model name is NOT written in: `glm-5.3` is these lanes' model and the
#: pattern has to hold for a lane running another.
BENIGN_PREAMBLE = (
    re.compile(r'^"[^"]*" is not a model this version of Claude Code '
               r'recognizes\b'),
    re.compile(r"^\[claude-code:[a-z_]+\]\s*\{"),
)

#: The reset instant the provider states inside its own message. OPTIONAL: a
#: refusal carrying none is reported with the reset UNKNOWN, and the reset is
#: never computed from the first failure plus five hours - that is the
#: hand-kept denominator, family 2.
_RESET = re.compile(r"(?i)limit will reset at\s*"
                    r"(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2}:\d{2})")

#: The request id the provider appends, whose first 14 characters are a
#: timestamp ON THE PROVIDER'S OWN CLOCK. This is a SECOND INDEPENDENT CLOCK
#: inside the same line, and reading it is what turns trap 6's hand check
#: into a measurement: across all eight refusals it sits 0-1s before the
#: watcher's own DONE line plus six hours. CORROBORATION ONLY - the
#: conversion below does not depend on it, and a request id that does not
#: parse leaves the conversion uncorroborated rather than unavailable.
_REQUEST_ID = re.compile(r"\[(\d{14})[0-9A-Za-z]*\]\s*$")

#: The provider's clock, as a UTC offset. THE ONE DECLARED FACT IN THIS
#: BLOCK, because the provider's message carries no zone at all: `08:07:16`
#: is Beijing time and means 02:07:16 here, and nothing in the string says
#: so. Operator-recorded in `CONTINUITY.md` trap 6, corroborated there by two
#: independent clocks and again here by `_REQUEST_ID`.
#:
#: DECLARED AS THE PROVIDER'S OFFSET AND NOT AS "SIX HOURS AHEAD", which is
#: the version that goes wrong silently. China keeps UTC+8 all year;
#: Europe/Zagreb is UTC+2 until 2026-10-25 and UTC+1 after, so the DELTA is
#: 6 today and 7 in nine days. The local half is therefore MEASURED from the
#: machine at the instant being converted, and never written down here.
PROVIDER_CLOCK_UTC_OFFSET_HOURS = 8

#: How far the corroborating clock may sit from where the declared offset
#: puts it. Far above the 0-1s measured between the provider's error line and
#: the watcher's DONE line, and far below the smallest zone error worth
#: catching - a quarter hour - so it cannot accept a wrong offset.
CLOCK_CORROBORATION_SECONDS = 120

#: How much of a `.out` is read. A file longer than this NECESSARILY carries
#: output beyond a refusal line and its preamble, so it cannot be a
#: never-started task. That is a statement about content EXISTING rather than
#: about how long it is, and it is the only place a length decides anything
#: in this block.
MAX_OUT_BYTES = 64 * 1024

#: How far after a START line its `.out` stamp may sit. `lane_watcher.ps1`
#: takes `$stamp = Get-Date` on the statement AFTER it logs START, so the
#: only disagreement possible is a second boundary - and measured, all nine
#: of 2026-10-16's closed tasks match to the second. The BOUND matters more
#: than the value: the watcher sleeps 5s between tasks, so a tolerance of 5
#: or more could capture the NEXT task's output.
OUT_JOIN_TOLERANCE_SECONDS = 2

#: How long a dispatched session may have been alive before "it never ran"
#: stops being supportable.
#:
#: DELIBERATELY NOT FITTED TO THE EIGHT ROWS IT IS MEASURED AGAINST. Their
#: elapsed times are 183, 185, 189, 191, 194, 1464, 3545 and 3559 seconds, so
#: any value between 195 and 1463 would split them into the comfortable 5 and
#: 3 - and a detector chosen that way is one fitted to its own sample, which
#: is the defect `classify_output`'s own docstring refuses below.
#:
#: This is instead `lane_watcher.ps1`'s own INTER-TASK SLEEP, the one interval
#: in this system that is independently known to be too short for a session to
#: do anything: it is the gap between a `MOVED` line and the next `START`, 5
#: seconds in every pair measured. A refusal inside it is provably
#: instantaneous. A refusal OUTSIDE it is UNKNOWN - never "probably
#: instantaneous too" - and on 2026-10-16 that is all eight of them, including
#: the five that took three minutes. The board's old glossary claimed NEVER
#: RAN for every one.
NEVER_RAN_WINDOW_SECONDS = 5

#: A cap on how many closed failures one page load will open a file for. The
#: log tail already bounds the events, but a long-lived log could hold
#: hundreds and a dashboard that opens hundreds of files is the slowest thing
#: on the machine. When it bites, the page SAYS the list is partial - a
#: silent cap on a do-all read is this repository's own named defect.
MAX_OUTCOMES = 200

#: The watcher's `MOVED` line, which names the DONE entry it created:
#: `MOVED 0067b-save-sweep.md -> 20261016-004231-exit1-0067b-save-sweep.md`.
#: THE STAMP IN IT IS THE SAME `$stamp` VARIABLE THE `.out` FILENAME USES, so
#: where this line exists it is an AUTHORITY for the join rather than an
#: inference from the START time. It is not always written: `glm-b` ran older
#: watcher bytes on 2026-10-16 that move the brief without logging it.
_MOVED = re.compile(r"^MOVED\s+(.+?) -> (\d{8}-\d{6})-")

#: The guard that bounded this incident, and the only reason the loss stopped
#: at nine briefs rather than the whole queue. It is a MITIGATION and the
#: board shows it as one; the watcher writes it immediately before going
#: down, so the DOWN verdict is unaffected by its being recognised here.
_GUARD = re.compile(r"^(\d+) consecutive failures\. Exiting rather than "
                    r"looping on a broken task\.?\s*$")

#: A task output's filename, as `lane_watcher.ps1` builds it:
#: `task-<lane>-<yyyyMMdd>-<HHmmss>.out`. The lane group is greedy and
#: backtracks, which is what makes `task-glm-b-20261016-014312.out` read as
#: lane `glm-b` rather than lane `glm`.
_OUT_NAME = re.compile(r"^task-(.+)-(\d{8}-\d{6})\.out$")

#: The stamp format shared by the `.out` filename and the DONE entry name.
_OUT_STAMP = "%Y%m%d-%H%M%S"


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
        moved = _MOVED.match(message)
        if moved:
            events.append({"kind": "moved", "at": stamp, "when": when,
                           "task": moved.group(1).strip(),
                           # The watcher's OWN `$stamp`, the same variable it
                           # built the `.out` filename from. An authority for
                           # the join rather than an inference from a clock.
                           "stamp": moved.group(2), "line": line})
            continue
        guard = _GUARD.match(message)
        if guard:
            events.append({"kind": "failure_guard", "at": stamp, "when": when,
                           "failures": int(guard.group(1)), "line": line})
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



# ----------------------------------- did this task run, or was it refused
#
# Everything here reads a CLOSED task's own output and nothing else. It
# writes nothing, moves nothing and restores nothing: a consumed brief is
# REPORTED, by name and by the path its copy sits at, and the move back into
# the queue is a person's.


def _read_out(path):
    """`(state, text, truncated, size)` for a task's `.out`. Four states.

    0 BYTES IS ITS OWN ANSWER AND IT IS NOT AN EMPTY TASK. The watcher
    redirects the task's stdout into this file, so it is 0 bytes for the
    whole run and fills at the end - 58 minutes at 0 bytes happened on a
    healthy task, and four of today's `.out` files are 0 bytes because their
    tasks are still running. For a CLOSED task 0 bytes means the output was
    lost, which is UNKNOWN. Nothing here ever looks at an open task's `.out`.
    """
    if not os.path.exists(path):
        return ABSENT, "", False, None
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as handle:
            blob = handle.read(MAX_OUT_BYTES)
    except OSError:
        return UNREADABLE, "", False, None
    if size == 0:
        return EMPTY, "", False, 0
    text = blob.decode("utf-8", "replace")
    if text.startswith("﻿"):
        text = text[1:]
    return PRESENT, text, size > MAX_OUT_BYTES, size


def classify_output(text, truncated=False):
    """What a closed task's own output says happened. CONTENT, AND NOTHING ELSE.

    Not the exit code, not the byte count, not the lane, not the model, not
    how many failures preceded it. Those are all available at the call site
    and not one of them is passed in, which is the point: on 2026-10-16 the
    eight refusals were all 713 bytes and all `exit1`, and both of those
    coincidences would have produced a detector that fires on the next
    ordinary failure.

    A refusal is claimed only when the output is a refusal line and nothing
    else but the harness's own preamble. Where a refusal line sits ON TOP of
    other output the task did run, so the verdict is an ordinary failure and
    `refusal_line_but_also_output` says why - the refusal line is still
    returned, so nothing is hidden by the stricter reading.
    """
    refusal, status, other = None, None, 0
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        match = _REFUSAL.match(stripped)
        if match:
            if refusal is None:
                refusal, status = stripped, match.group(1)
            # A second refusal line is more refusal, never other output.
            continue
        if any(pattern.match(stripped) for pattern in BENIGN_PREAMBLE):
            continue
        other += 1

    # `truncated` counts as other output: a file longer than the read cap
    # carries content past a refusal and its preamble by construction.
    also = bool(other) or bool(truncated)
    if refusal is not None:
        outcome = O_FAILED if also else O_REFUSED
    elif other or truncated:
        outcome = O_FAILED
    else:
        # Readable, non-empty, and holding not one line worth reading. That
        # is not an ordinary failure and it is certainly not a refusal: it is
        # a failure nobody can classify.
        outcome = O_UNKNOWN
    return {
        "outcome": outcome,
        "refusal_line": refusal,
        "status_code": status,
        "other_lines": other,
        "also_output": also,
        "refusal_line_but_also_output": bool(refusal and also),
    }


def local_utc_offset_hours(when):
    """This machine's UTC offset at `when`, or None. MEASURED, never declared.

    The watcher stamps local time with no zone and `_parse_stamp` reads it as
    local, so the local half of a timezone conversion has to come from the
    machine at the instant being converted - which is also what keeps it
    right across a DST change. `astimezone()` on a naive datetime treats it
    as local, which is exactly the assumption already in force here.
    """
    if when is None:
        return None
    try:
        offset = when.astimezone().utcoffset()
    except (OverflowError, OSError, ValueError):
        return None
    if offset is None:
        return None
    return offset.total_seconds() / 3600.0


def refusal_reset(line, local_offset_hours,
                  provider_offset_hours=PROVIDER_CLOCK_UTC_OFFSET_HOURS):
    """The reset instant a refusal states, on BOTH clocks, or UNKNOWN.

    A board that printed `08:07:16` and stopped would have handed the
    operator a trap: that is the provider's clock, it means 02:07:16 here,
    and the string itself says nothing about which. So the stated value is
    returned verbatim AND converted, and the conversion carries the two
    offsets it was computed from so a reader can check it.

    No reset stated means no reset returned. It is NEVER computed from the
    first failure plus five hours - the window is rolling and its start is
    not an event in any log we hold, so that number would be invented.
    """
    answer = {"stated": None, "local": None, "delta_hours": None,
              "provider_offset_hours": provider_offset_hours,
              "local_offset_hours": local_offset_hours}
    found = _RESET.search(line or "")
    if not found:
        return answer
    answer["stated"] = "%s %s" % found.groups()
    when = _parse_stamp(answer["stated"])
    if when is None or local_offset_hours is None:
        return answer
    delta = provider_offset_hours - local_offset_hours
    answer["delta_hours"] = delta
    answer["local"] = (when
                       - datetime.timedelta(hours=delta)).strftime(_STAMP)
    return answer


def corroborate_clock(line, done_when, delta_hours):
    """A SECOND CLOCK on the same line, against the offset just used.

    The provider appends a request id whose first 14 characters are a
    timestamp on its own clock. Where the declared offset is right, that
    timestamp lands on the watcher's DONE time plus the delta - measured
    0 to 1 second out across all eight of 2026-10-16's refusals.

    None means there is no second clock here, which is UNCORROBORATED and is
    not the same as CONTRADICTED. `agrees` False is the one that matters:
    it means the conversion above is resting on an offset this artifact does
    not support, and the page must stop claiming the local time.
    """
    if delta_hours is None or done_when is None:
        return None
    found = _REQUEST_ID.search((line or "").rstrip())
    if not found:
        return None
    try:
        stamp = datetime.datetime.strptime(found.group(1), "%Y%m%d%H%M%S")
    except ValueError:
        return None
    expected = done_when + datetime.timedelta(hours=delta_hours)
    drift = int(abs((stamp - expected).total_seconds()))
    return {
        "stamp": stamp.strftime(_STAMP),
        "expected": expected.strftime(_STAMP),
        "drift_seconds": drift,
        "tolerance_seconds": CLOCK_CORROBORATION_SECONDS,
        "agrees": drift <= CLOCK_CORROBORATION_SECONDS,
    }


def closed_failures(events):
    """Every DONE the watcher counted a FAILURE, paired with its own START.

    SCOPED TO FAILURES, and the gap is named rather than left implied: a
    `exit0` DONE is not opened, so a refusal that somehow exited 0 would not
    be seen here. The watcher's own rule makes that nearly unreachable - exit
    0 with no lane-file growth becomes NOWORK, which IS a failure suffix and
    IS examined - and the page states the gap where it shows this.

    THE START IS CARRIED BECAUSE IT IS THE FALLBACK JOIN. `open_start` is
    cleared on every DONE, so a DONE with no preceding START - the shape a
    truncated log tail produces - arrives with `start` None and is reported
    UNKNOWN rather than joined to whatever `.out` happened to be nearby.
    """
    pairs, open_start = [], None
    for index, event in enumerate(events):
        if event["kind"] == "start":
            open_start = event
        elif event["kind"] == "done":
            if event.get("suffix") != "exit0":
                pairs.append({"start": open_start, "done": event,
                              "index": index})
            open_start = None
    return pairs


def _moved_stamp(events, index, task):
    """The stamp the watcher itself wrote for this DONE, or None.

    Scanned forward only as far as the next START or DONE: a MOVED line
    belongs to the DONE immediately above it, and matching one further down
    the log would attach this brief to another task's stamp.
    """
    for event in events[index + 1:]:
        if event["kind"] in ("start", "done"):
            return None
        if event["kind"] == "moved" and event["task"] == task:
            return event["stamp"]
    return None


def out_files(logs_dir, lane):
    """`{stamp: filename}` for one lane's task outputs, or None if unreadable.

    None is the refusal, not `{}`: a directory that could not be listed holds
    no information about whether a task's output exists, and an empty dict
    would make every closed failure read as "output absent".
    """
    try:
        names = os.listdir(logs_dir)
    except OSError:
        return None
    found = {}
    for name in names:
        match = _OUT_NAME.match(name)
        if match and match.group(1) == lane:
            found[match.group(2)] = name
    return found


def join_out(candidates, moved_stamp, start_event):
    """Which `.out` belongs to this closed task, and ON WHOSE AUTHORITY.

    TWO PATHS, AND THE FIRST IS AN AUTHORITY RATHER THAN AN INFERENCE. The
    watcher builds the `.out` filename and the DONE entry name from one
    `$stamp` variable and writes that name into its MOVED line, so where the
    line exists the stamp is not guessed at all - and where the MOVED line
    names a stamp with no file behind it, the answer is ABSENT rather than a
    fall-through to the clock, because falling through would attach the wrong
    file.

    The second path is the START's own timestamp. `$stamp = Get-Date` runs on
    the statement after `Log "START ..."`, so the two can differ only across
    a second boundary; all nine of 2026-10-16's closed tasks match exactly.
    The window is bounded well under the watcher's 5s inter-task sleep, so it
    cannot reach the next task's output, and a window matching more than one
    file is AMBIGUOUS rather than resolved by picking the nearest.
    """
    answer = {"name": None, "stamp": None, "join": None, "ambiguous": [],
              "why": None}
    if candidates is None:
        answer["why"] = ("this lane's logs directory could not be listed, so "
                         "no task output could be located")
        return answer
    if moved_stamp:
        answer["stamp"] = moved_stamp
        answer["join"] = "the watcher's own MOVED line"
        answer["name"] = candidates.get(moved_stamp)
        if answer["name"] is None:
            answer["why"] = ("the MOVED line names stamp %s and no `.out` "
                             "with that stamp is there" % moved_stamp)
        return answer
    if start_event is None or start_event["when"] is None:
        answer["why"] = ("no START line is paired with this DONE, so there "
                         "is nothing to join its output to")
        return answer
    hits = []
    for offset in range(OUT_JOIN_TOLERANCE_SECONDS + 1):
        stamp = (start_event["when"]
                 + datetime.timedelta(seconds=offset)).strftime(_OUT_STAMP)
        if stamp in candidates:
            hits.append(stamp)
    if len(hits) == 1:
        answer["stamp"] = hits[0]
        answer["name"] = candidates[hits[0]]
        answer["join"] = ("this task's own START line, %s"
                          % start_event["at"])
        return answer
    if not hits:
        answer["why"] = ("no `.out` is stamped within %ds of this task's "
                         "START at %s" % (OUT_JOIN_TOLERANCE_SECONDS,
                                          start_event["at"]))
        return answer
    answer["ambiguous"] = [candidates[s] for s in hits]
    answer["why"] = ("%d task outputs are stamped within %ds of this task's "
                     "START, so none of them is provably this one"
                     % (len(hits), OUT_JOIN_TOLERANCE_SECONDS))
    return answer


def consumed_copy(root, lane, stamp, suffix, brief):
    """Where the watcher put the brief it consumed, read back rather than named.

    `Move-Item` preserves the bytes, so the copy in the DONE folder IS the
    brief - which is what makes a REFUSED verdict actionable instead of a
    post-mortem. The name is `<stamp>-<suffix>-<brief>`, built from the same
    `$stamp`, and the size here is a fresh `getsize` of that path and not an
    assumption that the move happened: the watcher logs its DONE line BEFORE
    attempting the move precisely because the move can be refused.

    THE PATH IS RETURNED RELATIVE TO THE ESTATE ROOT. The root is somebody's
    home directory and this page does not print it; the estate-relative path
    plus the root's name identifies the file unambiguously for whoever is
    standing in it.
    """
    answer = {"state": None, "name": None, "relative": None, "bytes": None}
    if not stamp:
        answer["state"] = UNKNOWN
        return answer
    name = "%s-%s-%s" % (stamp, suffix, brief)
    answer["name"] = name
    answer["relative"] = os.path.join("queue", lane, "DONE", name)
    path = os.path.join(root, "queue", lane, "DONE", name)
    if not os.path.exists(path):
        answer["state"] = ABSENT
        return answer
    try:
        answer["bytes"] = os.path.getsize(path)
        answer["state"] = PRESENT
    except OSError:
        answer["state"] = UNREADABLE
    return answer


def still_missing(brief, queued, inflight, queue_state, running_state):
    """Is the consumed brief back where a watcher can take it? THREE answers.

    True means it is not in the lane queue and not in RUNNING: the restore
    has not happened, or has not covered this one. False means it is back.
    None means one of the two directories could not be read - and an
    unreadable directory NEVER proves a brief missing, because that would
    send somebody to restore a file that is already there.
    """
    if brief in (queued or []) or brief in (inflight or []):
        return False
    if queue_state != PRESENT or running_state != PRESENT:
        return None
    return True


def restored_copy(root, lane, brief, queued, inflight):
    """Where a consumed brief is NOW, if it is back, and how big it is.

    The sizes matter because the restore was done BY HAND at 01:49 and
    nothing verified it except the session that did it. `Move-Item` preserves
    bytes, so the copy in the DONE folder and the copy back in the queue
    should agree exactly - and two sizes a reader can compare is evidence
    they do. It is NOT proof: nothing here hashes either file.
    """
    answer = {"state": ABSENT, "relative": None, "bytes": None}
    for where, names in (("", queued or []), ("RUNNING", inflight or [])):
        if brief not in names:
            continue
        parts = ["queue", lane] + ([where] if where else []) + [brief]
        answer["relative"] = os.path.join(*parts)
        path = os.path.join(root, *parts)
        try:
            answer["bytes"] = os.path.getsize(path)
            answer["state"] = PRESENT
        except OSError:
            answer["state"] = UNREADABLE
        return answer
    return answer


def _closed_outcome(root, lane, pair, events, candidates, queued, inflight,
                    queue_state, running_state, local_offset_hours):
    """One closed failure, classified, with the evidence line that did it."""
    done, start = pair["done"], pair["start"]
    brief = done["task"]
    moved = _moved_stamp(events, pair["index"], brief)
    joined = join_out(candidates, moved, start)

    if joined["name"] is None:
        out_state, text, truncated, size = (
            UNREADABLE if candidates is None else ABSENT), "", False, None
    else:
        out_state, text, truncated, size = _read_out(
            os.path.join(root, "logs", joined["name"]))

    if out_state == PRESENT:
        found = classify_output(text, truncated)
    else:
        # Absent, unreadable or 0 bytes. A failure that cannot be read cannot
        # be classified, and UNKNOWN never becomes a refusal and never
        # becomes an ordinary failure.
        found = {"outcome": O_UNKNOWN, "refusal_line": None,
                 "status_code": None, "other_lines": 0, "also_output": False,
                 "refusal_line_but_also_output": False}

    reset = refusal_reset(found["refusal_line"], local_offset_hours)
    corroboration = corroborate_clock(found["refusal_line"], done["when"],
                                      reset["delta_hours"])
    label, implies = OUTCOME_TEXT.get(found["outcome"], (None, None))

    # HOW LONG THIS SESSION WAS ALIVE, which is the only figure that can
    # refute "it never ran" - and the board asserted that on every refusal
    # for sixteen hours while holding both lines it needed to check it.
    #
    # The refusal line sits at the END of the output because `claude -p`
    # emits its result when it exits, and the request id in it lands within a
    # second of the DONE line on every row measured. So the whole START..DONE
    # interval is time in which the session was dispatched and its actions are
    # NOT in its output. `elapsed_seconds` is that interval, from the
    # watcher's own two lines.
    elapsed = _seconds_between(start["when"] if start else None, done["when"])
    # THREE ANSWERS AND None IS NOT True. None where either line is missing a
    # parseable stamp: an interval that could not be measured never licenses
    # the stronger claim. False is the claim being WITHDRAWN, not refuted -
    # the session may still have done nothing, and nothing here can say.
    never_ran = (None if elapsed is None
                 else elapsed <= NEVER_RAN_WINDOW_SECONDS)
    return {
        "lane": lane,
        "brief": brief,
        "at": done["at"],
        "date": done["at"][:10],
        "suffix": done.get("suffix"),
        # Verbatim. The DONE line IS the evidence for the misreport, and a
        # summary of it would be the misreport again in different words.
        "line": done["line"],
        "start_at": start["at"] if start else None,
        # Seconds between this task's own START and its own DONE, or None.
        # The whole window in which the session was alive and unrecorded.
        "elapsed_seconds": elapsed,
        # True only where that window is inside the watcher's inter-task
        # sleep, which is the one interval known to be too short to act in.
        "never_ran_supportable": never_ran,
        "never_ran_window_seconds": NEVER_RAN_WINDOW_SECONDS,
        "outcome": found["outcome"],
        "outcome_label": label,
        "outcome_implies": implies,
        "refusal_line": found["refusal_line"],
        "status_code": found["status_code"],
        "refusal_line_but_also_output": found["refusal_line_but_also_output"],
        "out_name": joined["name"],
        "out_join": joined["join"],
        "out_join_why": joined["why"],
        "out_ambiguous": joined["ambiguous"],
        "out_state": out_state,
        # Shown, never tested. 713 bytes is how a person recognises this at a
        # glance and trap 6 records the same refusal at 559.
        "out_bytes": size,
        "out_truncated": truncated,
        "reset": reset,
        "clock_check": corroboration,
        "consumed": consumed_copy(root, lane, joined["stamp"],
                                  done.get("suffix"), brief),
        "still_missing": still_missing(brief, queued, inflight, queue_state,
                                       running_state),
        "restored": restored_copy(root, lane, brief, queued, inflight),
    }


def closed_outcomes(root, lane, events, queued, inflight, queue_state,
                    running_state, local_offset_hours, cap=MAX_OUTCOMES):
    """Every closed failure in this lane's log window, newest last.

    `(rows, capped)`. The cap is on how many files are opened, and when it
    bites the OLDEST are dropped and `capped` is the count that was not
    examined - a page that silently examined 200 of 500 would be this
    repository's own named defect wearing a dashboard.
    """
    pairs = closed_failures(events)
    capped = max(0, len(pairs) - cap)
    candidates = out_files(os.path.join(root, "logs"), lane)
    rows = [_closed_outcome(root, lane, pair, events, candidates, queued,
                            inflight, queue_state, running_state,
                            local_offset_hours)
            for pair in pairs[capped:]]
    return rows, capped


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

# ---------------------------------------------------------------- the floor
#
# THE FLOOR IS NOT A CONSTANT IN THIS CODEBASE, and the first version of this
# module had it as one: `FLOOR = 3`, with a docstring saying the real
# authority was `queue/README.md`. That is the hand-kept denominator - failure
# family 2 in this estate's own catalogue - and it fails in the one direction
# that matters. The operator raises the floor in his own file, nothing here
# changes, the board goes on comparing against 3, and every lane reads
# compliant against a floor nobody is holding them to. A doc comment naming
# the authority is not the same as reading it.
#
# So it is read, and when it cannot be read the answer is UNKNOWN with the
# path named. An unknown floor produces no breach verdict at all - not a
# breach, and very much not compliance.

#: Where the operator writes it. Relative to the estate root, and joined
#: rather than written as a path so this says the same thing on both
#: platforms the reader has run on.
FLOOR_README = ("queue", "README.md")

#: Readable, and it states no floor. Distinct from ABSENT: the authority
#: exists and does not answer, which is a different thing to repair from the
#: authority not being there.
FLOOR_UNSTATED = "unstated"

#: Readable, and it states two different floors. UNKNOWN rather than
#: first-wins or lowest-wins, because either choice would be this reader
#: deciding an operator question quietly.
FLOOR_AMBIGUOUS = "ambiguous"

FLOOR_STATE_TEXT = {
    PRESENT: "read from the operator's own file",
    ABSENT: "that file is not there, so the floor is UNKNOWN - and it is NOT "
            "assumed to be 3",
    UNREADABLE: "that file could not be opened, so the floor is UNKNOWN - "
                "and it is NOT assumed to be 3",
    EMPTY: "that file has no bytes in it, so the floor is UNKNOWN",
    FLOOR_UNSTATED: "that file is readable and states no floor, so the floor "
                    "is UNKNOWN. An instrument that filled in 3 here would be "
                    "holding every lane to a number nobody wrote",
    FLOOR_AMBIGUOUS: "that file states more than one floor. UNKNOWN rather "
                     "than picking one, because which of them is in force is "
                     "the operator's answer and not this reader's",
}

#: The sentence as the operator writes it: `**Floor: never leave a lane below
#: 3 queued briefs.**`. Deliberately anchored on the whole clause rather than
#: on a bare number near the word "floor" - the same file carries "1 brief
#: queued", "3 briefs", "10 briefs" and "17 briefs" in its arithmetic
#: paragraph, and a loose pattern would read the floor off a worked example.
_FLOOR_SENTENCE = re.compile(
    r"(?i)never\s+leave\s+a\s+lane\s+below\s+(\d+)\s+queued\s+brief")


def read_floor(root):
    """`(state, floor, path, line)`. The operator's floor, from his own file.

    `floor` is an int only when `state` is PRESENT. Every other state means
    UNKNOWN, and the PATH is returned in all of them so a page can name the
    file it could not read instead of reporting a number it invented.

    The verbatim line comes back too, because a floor on a screen with no
    quotation beside it is a number the reader has to trust; with the
    sentence beside it, it is a number the reader can check.
    """
    path = os.path.join(root, *FLOOR_README) if root else None
    if path is None:
        return ABSENT, None, None, None
    if not os.path.exists(path):
        return ABSENT, None, path, None
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            text = handle.read()
    except OSError:
        return UNREADABLE, None, path, None
    if not text.strip():
        return EMPTY, None, path, None
    found = []
    for raw in text.splitlines():
        match = _FLOOR_SENTENCE.search(raw)
        if match:
            found.append((int(match.group(1)), raw.strip()))
    if not found:
        return FLOOR_UNSTATED, None, path, None
    distinct = {value for value, _ in found}
    if len(distinct) > 1:
        # Every one of them, so the page can show the operator the
        # disagreement in his own file rather than just refusing.
        return (FLOOR_AMBIGUOUS, None, path,
                " | ".join(line for _, line in found))
    return PRESENT, found[0][0], path, found[0][1]


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


# ------------------------------------------------- the machine-wide lock
#
# WHY THIS IS HERE, MEASURED 2026-10-16 AND NOT HYPOTHESISED. At 04:40 a
# session inside the `suppression` watcher took the machine-wide suite lock
# and launched that branch's full suite under pid 79556. At 04:45:37 the
# watcher logged `DONE 0220-...md -> exit0` and the session was gone. Two
# states follow from that and they need opposite things from a person:
#
#     79556 still running   the lock is held by nobody who will ever release
#                           it, and every other track's suite waits up to six
#                           hours behind it before raising `SuiteBusy`
#     79556 exited          the lock is free and NOBODY READ THE RESULT of a
#                           40-minute suite
#
# NEITHER WAS VISIBLE ANYWHERE IN THIS ESTATE. `qwen/0150` had already
# measured the suite lock as the bottleneck, and the one instrument that
# reads the process table is this module - so the lock belongs to it.
#
# THE STATE THE ESTATE HAD NO NAME FOR. `suitelock` itself has only two
# answers, because it only ever needs two: a lock it may take, and a lock it
# must wait for. A READER needs a third. A lock file whose holder is dead is
# not "held" - nothing will release it, no suite is running, and the next run
# will take it over and say so - and it is not "free" either, because until
# something tries, every waiter sits behind it. That is ORPHAN, and family 6
# of the failure catalogue is precisely an instrument meeting a result it has
# no name for and picking the nearest name it has. The nearest name here is
# "held", and it would hide the whole fact.
#
# WHAT THIS REFUSES TO DO. It clears nothing and kills nothing. It does not
# call `suitelock._live_tickets`, which is the obvious reader for the waiter
# queue and which DELETES a dead owner's ticket as it walks - a measuring
# instrument that prunes the thing it measures is not one. It parses ticket
# names with `suitelock._pid_of_ticket`, which is pure, because the ticket
# NAME FORMAT must have exactly one authority and that module owns it.

#: A lock whose holder is alive. The only state that means a suite is running.
LOCK_HELD = "lock_held"
#: No lock file, established by LISTING the directory rather than by a failed
#: open - see `_lock_listing` for why those are not the same question.
LOCK_FREE = "lock_free"
#: THE NEW ONE. Lock present, holder provably dead. Nothing will release it.
LOCK_ORPHAN = "lock_orphan"
#: Lock present, holder's liveness UNDETERMINABLE. Deliberately not ORPHAN:
#: claiming a holder dead on a failed read is how a live suite's lock gets
#: taken, which happened on 2026-10-02 and is the defect `DAMAGED_GRACE`
#: exists for.
LOCK_HELD_UNKNOWN = "lock_held_unknown"
#: The authority could not be consulted: path unresolved, directory
#: unlistable, file unreadable, content unparseable, or a holder with no
#: usable pid. NEVER rendered as FREE.
LOCK_UNKNOWN = "lock_unknown"

#: What each lock state means and what it does NOT license. The words travel
#: with the data so the page holds no table of its own, exactly as
#: `VERDICT_TEXT` does - and the five values are prefixed `lock_` so this
#: third vocabulary cannot collide with the verdict or outcome ones.
LOCK_TEXT = {
    LOCK_HELD: ("HELD",
                "a lock file names a pid and that pid is in the process "
                "table. One full suite is running on this machine and every "
                "other run waits - which is this lock working, not a fault"),
    LOCK_FREE: ("FREE",
                "the directory that holds the lock was LISTED and the lock "
                "file is not in it. A run starting now would get the lock "
                "immediately"),
    LOCK_ORPHAN: ("ORPHAN",
                  "a lock file is present and its holder is NOT in the "
                  "process table. No suite is running and nothing will ever "
                  "release this lock: the next run takes it over as stale "
                  "and announces the dead pid. Until one tries, every "
                  "waiter queues behind a holder that no longer exists"),
    LOCK_HELD_UNKNOWN: ("HELD, HOLDER UNKNOWN",
                        "a lock file names a usable pid and whether that pid "
                        "is alive could not be determined - the process "
                        "table could not be read. NOT orphan: a holder is "
                        "never called dead on a failed read, because that is "
                        "how a running suite's lock was stolen on "
                        "2026-10-02"),
    LOCK_UNKNOWN: ("UNKNOWN",
                   "the lock authority could not be consulted - its path "
                   "could not be resolved, its directory could not be "
                   "listed, its bytes could not be read, its content did not "
                   "parse, or it names no usable pid. A free lock and an "
                   "unreadable one are different facts and this is the "
                   "second one. UNKNOWN is never free, never idle and never "
                   "ok"),
}

#: The lock's own `started_at` and `queued_at` format, written by
#: `suitelock.acquire` with `time.strftime` - so LOCAL, naive, no zone. Read
#: against `datetime.datetime.now()`, which is the same clock.
LOCK_STAMP = "%Y-%m-%dT%H:%M:%S"

#: Name of the one lock this reads. A list of one, because the signature and
#: the page are per-lock: a second machine-wide lock arrives as another row
#: rather than as a rewrite.
SUITE_LOCK = "the full test suite"


def _lock_listing(file_path):
    """Is the lock file in its directory's listing? True / False / None.

    WHY THIS IS NOT `os.path.exists`. `exists` answers False both for "the
    lock is genuinely not there" and for "the directory cannot be reached",
    and those are the two facts this panel is required not to merge. A
    LISTING separates them: a listing that succeeds and does not hold the
    name PROVES absence, and a listing that fails proves nothing at all.

    `suitelock.read` cannot answer it either - it turns both into `None`,
    which is right for `acquire` (it will fail on the write) and wrong for a
    reader, which would print FREE.
    """
    try:
        names = os.listdir(os.path.dirname(file_path))
    except OSError:
        return None
    return os.path.basename(file_path) in names


def _lock_authority(file_path):
    """`(state, payload, why)` for the lock FILE. Liveness is a later question.

    The parse is `suitelock.read`'s, never a second one: that module owns the
    lock's format. What is added here is the split that a reader needs and
    `acquire` does not - `read` collapses "absent" and "unreachable" into
    `None`, and collapses every parse failure into `damaged`.
    """
    holder = suitelock.read(file_path)
    if holder is None:
        # `read` answers None for FileNotFoundError, which covers a missing
        # FILE and a missing DIRECTORY - and, because `json.load` of the four
        # bytes `null` also returns None, a lock file that parsed to nothing.
        present = _lock_listing(file_path)
        if present is None:
            return LOCK_UNKNOWN, None, (
                "the directory that would hold this lock could not be "
                "listed, so the lock's ABSENCE could not be established. An "
                "authority that cannot be consulted is UNKNOWN and is never "
                "FREE")
        if present:
            return LOCK_UNKNOWN, None, (
                "the lock file IS in the directory listing and reading it "
                "produced nothing - it was removed between the two reads, or "
                "its content is the JSON literal `null`. Either way no "
                "holder could be established from a file that is there")
        return LOCK_FREE, None, None
    if not isinstance(holder, dict):
        # Valid JSON that is not an object - a list, a string, a number.
        # `read` hands it straight back and every `.get` below would raise.
        return LOCK_UNKNOWN, None, (
            "the lock file parsed as JSON but not as an object, so it "
            "carries no holder. It is not a lock this reader understands and "
            "it is not an absent one")
    if holder.get("damaged"):
        return LOCK_UNKNOWN, holder, (
            "the lock file exists and its content could not be read or did "
            "not parse. `suitelock` treats this as takeable only after "
            "%.0fs, and this reader treats it as UNKNOWN for as long as it "
            "lasts - a damaged lock is not a free one"
            % suitelock.DAMAGED_GRACE)
    pid = holder.get("pid")
    # `isinstance(True, int)` is True in python, so the bool is excluded
    # explicitly: a lock whose pid field reads `true` names no process.
    if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
        return LOCK_UNKNOWN, holder, (
            "the lock file parses and names no usable pid (%r), so there is "
            "nothing whose liveness could be checked. A lock with no holder "
            "is UNKNOWN, never free" % (pid,))
    return LOCK_HELD, holder, None


def _lock_liveness(pid, probe, table):
    """`(alive, why)` for the holder. True, False, or None for UNDETERMINABLE.

    THE AUTHORITY IS THE PROCESS TABLE, NOT THE NUMBER IN THE FILE, and that
    distinction is the whole point: a pid in a lock file is a fact about the
    file, and `suitelock` has already been misled by one. Membership of the
    table is a fact about the machine.

    WHY THE TWICE-SAMPLED CPU DELTA IS NOT THIS ANSWER, stated because this
    estate's rule for a LANE's liveness is exactly that delta. A delta
    answers "is this process doing anything", and a suite blocked on a socket
    or a teardown accrues no measurable CPU in a five-second window while
    being perfectly alive. Making the delta the liveness test would therefore
    report a healthy holder as ORPHAN - which is how a live holder's lock was
    taken on 2026-10-02 - and, because a first sample has no delta at all, it
    would render every first page load HELD-UNKNOWN, hiding the one state
    this panel exists to show. So the two questions are kept apart and both
    are reported: the table answers EXISTENCE, the delta answers PROGRESS,
    and `_lock_cpu` below carries the second.

    The CPU probe is read here as a SECOND authority on existence rather than
    as the test: a pid in the table whose CPU can also be read is alive on
    two independent reads, and a pid in the table whose handle is refused is
    still alive - a process this cannot open is still a running process.
    """
    if table is None:
        return None, ("the process table could not be read on this "
                      "platform, so whether this holder is alive is UNKNOWN "
                      "- which is not dead and does not make this lock an "
                      "orphan")
    if int(pid) in table:
        return True, None
    return False, ("the pid in the lock file is not in the process table. "
                   "That holder is gone, so nothing will release this lock")


def _lock_cpu(pid, probe, table, now, samples, alive):
    """The holder's CPU seconds and the delta since the last look.

    PROGRESS, NEVER LIVENESS - see `_lock_liveness`. Same mechanics as
    `_cpu_reading`: the samples live in memory for the life of the process,
    so the first look has no delta and says so rather than inventing one.
    """
    reading = {"pid": pid, "seconds": None, "delta_seconds": None,
               "wall_seconds": None, "progressing": None, "why": None}
    if alive is not True:
        reading["why"] = ("the holder is not established alive, so there is "
                          "no process to sample")
        return reading
    seconds = probe.cpu(pid)
    if seconds is None:
        reading["why"] = ("this process is in the table and its CPU time "
                          "could not be read. Counted as alive and "
                          "unmeasured, never as zero")
        return reading
    reading["seconds"] = round(seconds, 1)
    key = ("suite.lock", pid)
    previous = samples.get(key)
    samples[key] = (now, reading["seconds"])
    if not previous:
        reading["why"] = ("first sample in this process - there is nothing "
                          "to compare it with. Load this page again for a "
                          "delta")
        return reading
    then, before = previous
    delta = round(reading["seconds"] - before, 1)
    wall = _seconds_between(then, now)
    if delta < 0:
        # A process's accumulated CPU cannot fall. Windows reuses a pid, so
        # the honest reading is that this is not the process that was
        # sampled - which also means the lock's holder may be gone.
        reading["why"] = ("the CPU sample went BACKWARDS, so this is not the "
                          "process the previous sample measured. Windows "
                          "reuses a pid, and a lock file naming a reused one "
                          "names somebody else's process")
        return reading
    if not wall:
        reading["why"] = ("the previous sample is from this same second, so "
                          "there is no window to measure across. Load this "
                          "page again in a moment")
        return reading
    reading["delta_seconds"] = delta
    reading["wall_seconds"] = wall
    # A real measurement either way. False here does NOT mean dead and must
    # never be rendered as one: it means this holder burned no measurable CPU
    # across the window, which for a running test suite is worth a look.
    reading["progressing"] = delta > 0
    return reading


def _lock_waiters(file_path, probe, table):
    """Who is queued behind this lock, read-only.

    `suitelock._live_tickets` is the obvious reader and is REFUSED: it
    unlinks a dead owner's ticket as it walks, and an instrument that prunes
    what it measures is not one. The ticket NAME is parsed with that module's
    own `_pid_of_ticket` so the format keeps exactly one authority.

    A WAITER'S LIVENESS GOES THROUGH `_lock_liveness`, and that is not a
    tidy-up. The first version of this function asked `int(pid) in table`
    inline, which is a SECOND implementation of the one question this panel
    turns on - and the mutation run proved it was a second one rather than
    arguing it: mutating `_lock_liveness` to always-answer-alive left both
    waiter controls GREEN, so for three figures on this page the probe was
    not being watched by anything. Two implementations of one rule drift, and
    the drift here would be silent.
    """
    directory = suitelock._queue_dir(file_path)
    try:
        names = sorted(os.listdir(directory))
    except FileNotFoundError:
        # No queue directory means nothing has ever waited here. That IS a
        # measurement, unlike the next branch.
        return {"state": ABSENT, "tickets": [], "alive_count": 0,
                "dead_count": 0, "unknown_count": 0, "foreign": 0}
    except OSError:
        return {"state": UNREADABLE, "tickets": None, "alive_count": None,
                "dead_count": None, "unknown_count": None, "foreign": None}
    tickets, foreign = [], 0
    for name in names:
        pid = suitelock._pid_of_ticket(name)
        if pid is None:
            # Not one of ours. Counted and left entirely alone - this
            # directory is not ours to tidy OR to interpret.
            foreign += 1
            continue
        alive, _why = _lock_liveness(pid, probe, table)
        tickets.append({"pid": pid, "alive": alive})
    return {
        "state": EMPTY if not names else PRESENT,
        "tickets": tickets,
        "alive_count": len([t for t in tickets if t["alive"] is True]),
        # A ticket whose owner is gone. `acquire` prunes these as it walks;
        # this reader only names them.
        "dead_count": len([t for t in tickets if t["alive"] is False]),
        "unknown_count": len([t for t in tickets if t["alive"] is None]),
        "foreign": foreign,
    }


def _lock_path_tail(file_path, parts=3):
    """The last few components of a path. NEVER the absolute one.

    The brief requires the path to be PRINTED wherever a lock renders
    UNKNOWN, because an UNKNOWN with no path is unactionable. This estate's
    other rule is that a screen never prints an absolute path - it is
    somebody's home directory in a screenshot. The tail satisfies both:
    `resonate-group-automation\\work\\suite.lock` names the authority
    precisely enough to find it and names nobody's home directory.
    """
    if not file_path:
        return None
    chunks = [c for c in re.split(r"[\\/]+", str(file_path)) if c]
    return os.path.join(*chunks[-parts:]) if chunks else None


def lock_row(probe=None, table=None, now=None, samples=None, file_path=None,
             name=SUITE_LOCK):
    """One lock, one row, and every value with the authority that produced it.

    Side-effect-free. Nothing is created, written, unlinked or renamed, in
    the lock's directory or in its ticket queue.
    """
    now = now or datetime.datetime.now()
    probe = probe or SystemProbe()
    samples = _SAMPLES if samples is None else samples
    row = {
        "name": name,
        # Both, because they answer different questions. `path_resolved` is
        # whether this reader could establish WHERE the lock is at all, and
        # a False there is an UNKNOWN that no amount of reading can fix.
        "path": None, "path_shown": None, "path_resolved": None,
        "state": LOCK_UNKNOWN, "state_label": None, "state_why": None,
        "why": None,
        "pid": None, "alive": None, "alive_why": None,
        "cpu": None,
        "branch": None, "worktree_shown": None,
        "started_at": None, "held_seconds": None,
        "queued_at": None, "queue_wait_seconds": None,
        # The lock records the path it was PUBLISHED to. If that disagrees
        # with the path resolved now, the lock has become per-worktree, which
        # is the exact defect `suitelock` was written to prevent - so it is
        # measured rather than assumed away.
        "recorded_path_shown": None, "path_agrees": None,
        "waiters": None,
        "remedy": None,
    }
    if file_path is None:
        try:
            file_path = suitelock.path()
        except Exception:                                      # noqa: BLE001
            file_path = None
    if not file_path:
        row["path_resolved"] = False
        row["state_label"], row["state_why"] = LOCK_TEXT[LOCK_UNKNOWN]
        row["why"] = ("the lock's own path could not be resolved, so there "
                      "is no authority to read. `suitelock.path()` answers "
                      "from `git rev-parse --git-common-dir`, and a reader "
                      "that guessed a path instead would be reading a "
                      "DIFFERENT lock from the one every suite takes")
        return row
    row["path"] = file_path
    row["path_shown"] = _lock_path_tail(file_path)
    row["path_resolved"] = True

    state, holder, why = _lock_authority(file_path)
    row["why"] = why
    if holder:
        row["branch"] = holder.get("branch")
        row["worktree_shown"] = _lock_path_tail(holder.get("worktree"), 1)
        row["started_at"] = holder.get("started_at")
        row["queued_at"] = holder.get("queued_at")
        recorded = holder.get("lock_path")
        if isinstance(recorded, str) and recorded:
            row["recorded_path_shown"] = _lock_path_tail(recorded)
            row["path_agrees"] = (os.path.normcase(os.path.abspath(recorded))
                                  == os.path.normcase(
                                      os.path.abspath(file_path)))
        row["held_seconds"] = _lock_elapsed(holder.get("started_at"), now)
        row["queue_wait_seconds"] = _lock_elapsed(holder.get("queued_at"),
                                                  now)

    if state == LOCK_HELD:
        pid = int(holder["pid"])
        row["pid"] = pid
        alive, alive_why = _lock_liveness(pid, probe, table)
        row["alive"], row["alive_why"] = alive, alive_why
        row["cpu"] = _lock_cpu(pid, probe, table, now, samples, alive)
        if alive is True:
            state = LOCK_HELD
        elif alive is False:
            # THE STATE THE ESTATE HAD NO NAME FOR.
            state = LOCK_ORPHAN
        else:
            state = LOCK_HELD_UNKNOWN

    row["state"] = state
    row["state_label"], row["state_why"] = LOCK_TEXT[state]
    row["waiters"] = _lock_waiters(file_path, probe, table)
    row["remedy"] = _lock_remedy(state, row)
    return row


def _lock_elapsed(stamp, now):
    """Seconds between a lock stamp and `now`, or None. Never a guess.

    A negative answer is returned as-is rather than clamped to zero: a lock
    stamped in the future is a real condition - a clock that moved - and a
    clamp would hide it behind a plausible number.
    """
    if not isinstance(stamp, str) or not stamp.strip():
        return None
    try:
        when = datetime.datetime.strptime(stamp.strip(), LOCK_STAMP)
    except ValueError:
        return None
    return int((now - when).total_seconds())


#: The exact commands a person runs. PROSE, carried to the page and to the
#: lane file, and there is deliberately no route, button or form behind any
#: of them: this panel reports, and clearing a lock or killing a holder is an
#: operator action on a machine-wide resource.
def _lock_remedy(state, row):
    if state == LOCK_ORPHAN:
        return ("Nothing will release this lock. Confirm the holder is gone "
                "and then remove the file BY HAND - the next suite would "
                "also take it over as stale and say so, which is the "
                "cheaper route if one is due: "
                "`Get-CimInstance Win32_Process -Filter \"ProcessId=%s\"` "
                "then `Remove-Item '%s'`"
                % (row["pid"], row["path_shown"]))
    if state == LOCK_UNKNOWN:
        return ("Read the authority yourself before doing anything: "
                "`Get-Content '%s'`. Do NOT remove it on an unreadable "
                "read - a damaged lock may belong to a running suite, which "
                "is why `suitelock` waits %.0fs before calling one takeable."
                % (row["path_shown"] or "<path unresolved>",
                   suitelock.DAMAGED_GRACE))
    if state == LOCK_HELD_UNKNOWN:
        return ("Do nothing yet. The holder's liveness is unknown and a lock "
                "is never cleared on a failed read. Check pid %s by hand: "
                "`Get-CimInstance Win32_Process -Filter \"ProcessId=%s\"`, "
                "and verify the reader works in the same call with "
                "`(Get-CimInstance Win32_Process | Measure-Object).Count` - "
                "`tasklist` through a bash tool returns zero rows for every "
                "query and a live pid then reads as GONE."
                % (row["pid"], row["pid"]))
    return None


def locks(probe=None, table=None, now=None, samples=None, file_path=None):
    """Every machine-wide lock, one row each, and nothing free by omission.

    A list of one today. The signature is per-lock rather than
    suite-lock-shaped so a second machine-wide lock arrives as another row.
    """
    now = now or datetime.datetime.now()
    probe = probe or SystemProbe()
    samples = _SAMPLES if samples is None else samples
    if table is None:
        table = probe.table()
    rows = [lock_row(probe=probe, table=table, now=now, samples=samples,
                     file_path=file_path)]
    return {
        "at": now,
        # None means the process table could not be read, so no holder's
        # liveness could be established. Said once rather than per row.
        "table_read": table is not None,
        "rows": rows,
        "held": len([r for r in rows if r["state"] == LOCK_HELD]),
        "free": len([r for r in rows if r["state"] == LOCK_FREE]),
        "orphan": len([r for r in rows if r["state"] == LOCK_ORPHAN]),
        # The two UNKNOWNs, kept apart: one has a usable holder it could not
        # check, the other has no usable authority at all.
        "held_unknown": len([r for r in rows
                             if r["state"] == LOCK_HELD_UNKNOWN]),
        "unknown": len([r for r in rows if r["state"] == LOCK_UNKNOWN]),
        "glossary": [{"state": key, "label": label, "why": why}
                     for key, (label, why) in sorted(LOCK_TEXT.items())],
    }


def board(root=None, now=None, probe=None, samples=None,
          local_offset_hours=None, lock_path=None):
    """One row per lane, and every unanswerable question answered UNKNOWN.

    `root` defaults to `ops_root()`. When nothing has said where the estate
    is, the board is UNCONFIGURED and names the variable - which is not
    "there are no lanes" and must not render as a clean empty table.
    """
    now = now or datetime.datetime.now()
    # MEASURED FROM THE MACHINE, at `now`, and only used to put a provider's
    # zoneless reset string onto this estate's clock. Passed in by a test so
    # the conversion is deterministic there; never written down as a constant,
    # because the delta it feeds changes with this machine's DST.
    if local_offset_hours is None:
        local_offset_hours = local_utc_offset_hours(now)
    probe = probe or SystemProbe()
    samples = _SAMPLES if samples is None else samples
    root = root or ops_root()

    if root is None:
        return {"state": UNCONFIGURED, "root": None, "variable": OPS_DIR,
                "lanes": [], "table_read": None, "at": now,
                "locks": locks(probe=probe, now=now, samples=samples,
                               file_path=lock_path)}
    if not os.path.isdir(root):
        return {"state": ABSENT, "root": root, "variable": OPS_DIR,
                "lanes": [], "table_read": None, "at": now,
                "locks": locks(probe=probe, now=now, samples=samples,
                               file_path=lock_path)}

    # READ ONCE, PER RENDER, AND PASSED DOWN. One reading for every lane, so
    # seven rows cannot be judged against two different floors because the
    # file was edited mid-render - and one authority travelling with the data
    # rather than seven lookups that could disagree.
    floor_state, floor, floor_path, floor_line = read_floor(root)

    table = probe.table()
    rows = []
    for lane, where in lane_names(root):
        rows.append(_lane_row(root, lane, where, probe, table, now, samples,
                              local_offset_hours, floor))

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
        # holds no copy of it and the two cannot drift. None is UNKNOWN, and
        # the three fields beside it are what a page prints instead of a
        # number it would otherwise have had to invent.
        "floor": floor,
        "floor_state": floor_state,
        "floor_path": floor_path,
        "floor_line": floor_line,
        # The offset the reset conversions used, so a reader can check one by
        # hand. None means it could not be measured, and then no refusal on
        # this board claims a local reset time.
        "local_offset_hours": local_offset_hours,
        "provider_offset_hours": PROVIDER_CLOCK_UTC_OFFSET_HOURS,
        # THE MACHINE-WIDE LOCK. Not a lane fact and not scoped to the
        # estate root - it is read in all three branches above, because a
        # lock panel that vanished when LANE_OPS_DIR was unset would be
        # one more invisible state. The table read above is passed in so
        # one render means one snapshot of the process table.
        "locks": locks(probe=probe, table=table, now=now,
                       samples=samples, file_path=lock_path),
    }


def _lane_row(root, lane, where, probe, table, now, samples,
              local_offset_hours=None, floor=None):
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

    # EVERY CLOSED FAILURE, OPENED AND CLASSIFIED. This is the layer that
    # tells a task that RAN AND FAILED from one that NEVER STARTED, and it is
    # read from each task's own output rather than from the suffix - because
    # `exit1` is the only word the watcher had for both, and it is the word
    # that consumes the brief. Computed after the queue listing because
    # whether a consumed brief is still missing is answered from it.
    outcomes, outcomes_capped = closed_outcomes(
        root, lane, events, queued, inflight, queue_state, running_state,
        local_offset_hours)
    refused = [row for row in outcomes if row["outcome"] == O_REFUSED]
    # The guard that bounded the 2026-10-16 loss at nine briefs instead of
    # the whole queue. Shown as the mitigation it is, and never as a fault.
    guards = [event for event in events if event["kind"] == "failure_guard"]

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

    # Is the process the pid file names in the table at all? None when the
    # table could not be read or no file names a pid. A dead watcher is the
    # root answer to "is this lane consuming work", and it is invisible in
    # the log: the log's last line looks the same either way.
    watcher_alive = (None if (table is None or root_pid is None)
                     else root_pid in table)
    # The log stopped moving. Only asked where the log says IDLE, because a
    # watcher mid-task is legitimately quiet for as long as the task runs -
    # an idle one is documented to heartbeat every five minutes.
    gone_quiet = bool(status == IDLE and silence is not None
                      and silence > IDLE_HEARTBEAT_SECONDS * 2)

    # DOWN HAS TWO DISJUNCTS AND ONLY THE FIRST WAS BUILT, which made this
    # reader document a check it did not make: `VERDICT_TEXT[V_DOWN]` has
    # promised "or the log has not moved and no watcher pid is live" since
    # the verdict was added, and nothing computed it. The common way a
    # watcher dies writes no `watcher down` line at all - `Stop-Process`
    # takes it and the log simply stops - and in that state this returned
    # IDLE while already holding both halves of the answer: `watcher_alive`
    # False, and `_cpu_reading`'s own text "that watcher is gone, so this
    # lane is consuming nothing whatever its log last said". Measured
    # 2026-10-16.
    #
    # `watcher_alive is False` and never a falsy test: None means the table
    # could not be read or no file names a pid, and an unknown liveness must
    # not produce DOWN any more than it produces healthy.
    #
    # BOTH halves are required, as the brief writes it. Inside the heartbeat
    # tolerance a watcher that has just died and one that is about to write
    # its next line are not distinguishable, so the verdict waits - and the
    # row carries `watcher_alive` either way, so nothing is hidden while it
    # does.
    #
    # STALLED is NOT collapsed into this. A lane with an open task and a
    # dead watcher has a brief sitting in RUNNING that a person has to move,
    # and that is the more actionable word; `gone_quiet` is false there
    # anyway, because the log is not IDLE.
    logged_down = bool(last_event and last_event["kind"] == "down")
    went_down = logged_down or (watcher_alive is False and gone_quiet)
    # Reported as "this verdict RESTS on inference", not as "the second
    # disjunct also holds". A watcher that logged `watcher down` and has
    # since left the table satisfies both, and saying so would make the
    # renderer explain an inference where it could simply quote the line.
    inferred_down = bool(went_down and not logged_down)

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
        # The floor is the operator's, from `queue/README.md`, read by
        # `read_floor` and handed in. None when the depth is unknown - an
        # unreadable queue is not a breach and is not compliance either - and
        # None when the FLOOR is unknown, for the same reason read the other
        # way round: a breach is a comparison and a comparison needs both
        # sides. Neither case is allowed to fall back on a constant.
        "below_floor": (None if depth is None or floor is None
                        else depth < floor),
        "floor": floor,
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
        # WHICH DISJUNCT FIRED, kept apart. `watcher_went_down` stays the
        # LOG's own claim and is never set by inference, so a reader is
        # never told the watcher logged something it did not.
        "watcher_went_down": logged_down,
        # True only where DOWN RESTS on the inference: no `watcher down`
        # line exists, and the verdict comes from a silent log crossed with
        # an absent pid. The renderer explains itself when this is set and
        # quotes the log line when it is not.
        "watcher_inferred_down": inferred_down,
        "watcher_alive": watcher_alive,
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
        "log_has_gone_quiet": gone_quiet,
        "log_state": log_state,
        "log_truncated": truncated,
        "records": len(events),
        "watcher_pid_state": pid_state,
        "watcher_pid": root_pid,
        "watcher_image_ok": watcher_image_ok,
        "cpu": cpu,
        # ------------------------------------- what each closed failure was
        "closed_failures": outcomes,
        # The count NOT examined, because the file-open cap bit. 0 normally;
        # a page that quietly examined some of them would be the silent cap
        # this repository has a family for.
        "closed_failures_capped": outcomes_capped,
        "refused": refused,
        "refused_count": len(refused),
        # Kept apart from the refusal count on purpose: a failure whose
        # output could not be read is NOT a refusal and is not an ordinary
        # failure either, and a reader has to see how many of those there are
        # before trusting the refusal total.
        "unclassifiable_failures": len([row for row in outcomes
                                        if row["outcome"] == O_UNKNOWN]),
        "briefs_still_missing": len([row for row in refused
                                     if row["still_missing"] is True]),
        "briefs_missing_unknown": len([row for row in refused
                                       if row["still_missing"] is None]),
        # The watcher's own `N consecutive failures. Exiting ...` line, when
        # it wrote one. A mitigation, not a fault - it is the only reason the
        # loss stopped where it did.
        "failure_guard": ({"at": guards[-1]["at"],
                           "failures": guards[-1]["failures"],
                           "line": guards[-1]["line"]} if guards else None),
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
