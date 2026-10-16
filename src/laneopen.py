"""The open ``START``: is anyone still listening?

WHAT THIS ANSWERS AND WHY NOTHING ANSWERED IT BEFORE. ``LANE_DEADLINE`` lets a
task ask *can I finish?*. Nothing let it ask *is anyone still listening?*
``CONTINUITY.md`` section 4 filed that check under trap 13 on 2026-10-16 and
nobody built it; ``webapp/0270`` section 6 filed it again, as one of two
absence shapes, and said why it was out of that brief's width:

    a dispatch with no ``DONE`` line is never asked the landing question at
    all, because ``src.lanerework`` keys on ``row["done_suffix"]`` and an open
    ``START`` has no suffix to key on.

So this module is NOT a second landing classifier and deliberately shares no
word with one. ``src.lanerework`` answers *did the work land*, of a dispatch
that ENDED. This answers *is this dispatch still owned*, of a dispatch that did
not end. A row here says nothing whatever about whether any work landed, and
the vocabulary is kept disjoint so that a reader cannot carry one answer across
to the other: nothing here is ``landed``, ``lost`` or ``not_determined``, and
nothing here is the board's ``running``, ``stalled`` or ``idle`` either.

THE NAIVE CHECK WOULD HAVE BEEN WRONG TWICE ON THE DAY IT WAS WRITTEN. Read
*"an open START older than the timeout means the lane is lost"* and two healthy
lanes are called dead - ``CONTINUITY.md`` section 4 trap 14, measured 14:42 to
14:59 on 2026-10-16:

    webapp       START 0260  13:55:17, no ending at 14:48, and HEALTHY -
                 it wrote webapp-0270-entry.md at 14:42:02
    suppression  START 0398  14:12:53, no ending at 14:48, and HEALTHY -
                 it wrote TASK-0399\\patch0399.py at 14:48:48

Both are the self-dispatch shape: a standing rule tells a finished lane to take
its lane's next brief, the watcher only ever moves the brief IT dispatched, and
so a live session sits under an open ``START`` for far longer than that brief's
own span while working perfectly. Elapsed time cannot tell that apart from a
lane whose supervisor died, and neither can the ``.out``'s byte count:
``qwen/0177`` took the coded ``TIMEOUT`` path, landed all its work, and left a
``.out`` of **0 bytes**, which is byte-identical to trap 13's.

THE THREE AUTHORITIES, AND WHAT EACH IS LICENSED FOR:

    the log's own records   whether this dispatch has a coded ending, and
                            whether the watcher has since dispatched ANOTHER
                            task - which is the one answer that needs no
                            process table at all
    the process table       whether a child of this lane's watcher is burning
                            CPU, sampled TWICE. One sample is not an answer;
                            ``CONTINUITY.md`` section 3 is explicit that
                            liveness is a rising CPU figure
    the estate's own files  whether something was written since the START
                            naming a DIFFERENT task id, which is the positive
                            signature of a session running past its brief

FAIL CLOSED, IN BOTH DIRECTIONS, BECAUSE BOTH GUESSES COST SOMETHING. An
unmeasurable liveness is ``OPEN_UNDETERMINED`` and never ``OPEN_ALIVE`` - an
instrument that cannot report its own blindness reports clean, which is failure
family five. And it is never a dead verdict either, because ``CONTINUITY.md``
section 4 trap 1 is explicit that **re-queuing is what loses the work**: on
2026-10-15 at 23:05 two watchers died, both orphaned tasks ran through their
whole queues, and the work was all there until somebody re-queued it. Every
verdict here that reports an absence of liveness therefore carries
``what_to_do`` text that says read the lane file and the ``.out`` FIRST.

WHAT THIS MODULE DOES NOT DO. It opens no socket, starts no process, signals
nothing and writes nothing. Liveness is a READ: the CPU figure comes from
``src.lanes``'s probe, which the board already owns, and no pid is ever sent a
signal. It also never promotes a row on a lane file's mtime - ``webapp/0250``'s
rule, that the mtime may demote and never promote, is kept by construction:
the mtime is only ever consulted AFTER liveness is already proven, and the
state it can reach (``OPEN_PAST_BRIEF``) is a refinement of ``OPEN_ALIVE``
rather than a claim that anything landed.
"""
import datetime
import os
import re


def _rework():
    """`src.lanerework`, imported at CALL time. The cycle is deliberate.

    `src.lanerework` imports `src.lanes`, and `src.lanes` imports this
    module to put the cell on each board row - so one of the three edges has
    to be deferred, and this is the right one to defer. The three things
    borrowed are the id and heading readers, and they are borrowed rather
    than copied because `0234` versus `0234b` has to have exactly one
    implementation in this repository: a second one is how a figure drifts.
    """
    from src import lanerework
    return lanerework


# --------------------------------------------------------------- the verdicts
#
# Five, ordered, mutually exclusive, and named in this module's own words. A
# sixth would be cheaper than reusing one of ``src.lanerework``'s and that is
# the trade this makes deliberately: failure family six is an instrument
# meeting a result it has no name for and filing it under the nearest name it
# has, and "the nearest name it has" is exactly how an open START became a
# landing question nobody asked.

#: A child of this lane's watcher burned measurably more CPU between two
#: samples. The only state that PROVES somebody is listening.
OPEN_ALIVE = "open_alive"

#: Alive, AND something naming a different task id was written since the
#: START. Trap 14's shape: the session finished its brief, took the next one
#: under the standing rule, and the watcher will never consume either.
OPEN_PAST_BRIEF = "open_alive_past_brief"

#: Nothing is listening and nothing will be. Trap 13's shape. NOT a
#: licence to re-queue - see ``WHAT_TO_DO`` below and trap 1.
OPEN_NO_LIVENESS = "open_no_liveness"

#: No ending yet, no liveness proven, and this lane's own deadline has not
#: passed. The watcher is still there and its own timeout is still due to
#: fire, so there is nothing for a person to do yet.
OPEN_WITHIN_DEADLINE = "open_within_deadline"

#: The liveness sample could not be taken, or could be taken and proves
#: neither way. Never ALIVE and never DEAD.
OPEN_UNDETERMINED = "open_undetermined"

#: Worst first. A lane's cell reports the worst of its open rows, because a
#: lane with one abandoned dispatch and one healthy one needs the abandoned
#: one on the screen.
OPEN_ORDER = (OPEN_NO_LIVENESS, OPEN_UNDETERMINED, OPEN_PAST_BRIEF,
              OPEN_ALIVE, OPEN_WITHIN_DEADLINE)

OPEN_TEXT = {
    OPEN_ALIVE: (
        "OPEN, ALIVE",
        "this dispatch has no coded ending, and a process under this lane's "
        "watcher burned measurably more CPU between two samples"),
    OPEN_PAST_BRIEF: (
        "OPEN, ALIVE, PAST BRIEF",
        "alive, and something naming a DIFFERENT task id has been written "
        "since this START - the session has gone on past the brief it was "
        "dispatched with, so neither brief will be consumed by the watcher"),
    OPEN_NO_LIVENESS: (
        "OPEN, NO LIVENESS",
        "this dispatch has no coded ending and nothing is listening for it: "
        "no `DONE` line will ever be written for this brief"),
    OPEN_WITHIN_DEADLINE: (
        "OPEN, WITHIN TIMEOUT",
        "no ending yet, no liveness proven, and this lane's own deadline has "
        "not passed - the watcher's own timeout is still due to fire"),
    OPEN_UNDETERMINED: (
        "UNDETERMINED",
        "the liveness sample could not be taken, or was taken and proves "
        "neither way. This is not ALIVE and it is not DEAD"),
}

#: What a person does about each. Separate from the WHY because the two get
#: read at different moments, and because the only dangerous cell on this
#: page is an absence of liveness that reads as permission to re-queue.
WHAT_TO_DO = {
    OPEN_ALIVE: "nothing. Let it work.",
    OPEN_PAST_BRIEF:
        "nothing to the running session. When it ends, the brief it ran past "
        "will still be sitting in `queue/<lane>/` with no START and no DONE "
        "line, and will be dispatched again against work already recorded - "
        "move it to `DONE/` by hand as `<stamp>-SELFTAKEN-<name>`, never with "
        "an `exit` token in the name.",
    OPEN_NO_LIVENESS:
        "DO NOT RE-QUEUE THE BRIEF FIRST. Trap 1: re-queuing is what loses "
        "the work. Read `LANE-<lane>.md` and this dispatch's `.out` - a 0-byte "
        "`.out` is normal mid-run and says nothing - then move the brief out "
        "of `RUNNING/` by hand so the lane can take its next one.",
    OPEN_WITHIN_DEADLINE:
        "nothing yet. Look again after this lane's own deadline passes.",
    OPEN_UNDETERMINED:
        "load this page again, or read the reason on the row - it names the "
        "one authority that could not be read.",
}


# ---------------------------------------------------------------- liveness
#
# NINE NAMED READINGS AND NOT ONE BOOLEAN, because the four ways of having no
# answer are four different repairs and a single `False` would make all four
# look like a dead lane. The grouping underneath is where the three-way
# ALIVE / ABSENT / UNDETERMINED decision is actually made, and it is a table
# rather than a chain of ifs so that adding a reading forces a choice.

#: Two samples, and the subtree's CPU went up. The only proof of life.
L_ROSE = "cpu_rose"
#: Two samples and no rise. NOT dead: a session waiting on an API burns no
#: measurable CPU, and `conhost.exe` is a child of every watcher.
L_FLAT = "cpu_did_not_rise"
#: First look in this process. There is no delta to read yet.
L_ONE_SAMPLE = "one_sample_only"
#: The watcher has since dispatched a LATER task. Needs no process table:
#: the watcher runs one task at a time, so it has demonstrably stopped
#: listening for this one and no process can be attributed to it either.
L_SUPERSEDED = "superseded_by_a_later_start"
#: The pid file names a process that is not in the table.
L_WATCHER_GONE = "watcher_pid_not_in_the_table"
#: The table was read, the watcher is in it, and nothing is under it. A real
#: measurement of absence rather than an absence of measurement.
L_NO_CHILD = "nothing_under_the_watcher"
#: The table could not be read on this platform.
L_NO_TABLE = "process_table_unreadable"
#: No file names this lane's watcher, so there is no root to walk from.
L_NO_PID = "no_watcher_pid_file"
#: Processes are there and not one of them could be opened for a CPU figure.
L_CHILD_UNREADABLE = "children_unreadable"

#: ALIVE: somebody is provably listening.
LIVE = "alive"
#: ABSENT: nobody is listening, established by a positive measurement.
ABSENT = "absent"
#: Neither established. The only honest third answer.
UNDETERMINED = "undetermined"

#: The whole three-way decision, as data. Every reading above appears exactly
#: once; `_group` raises on one that does not, so a reading added without a
#: group cannot quietly default to the safest-looking bucket.
LIVENESS_GROUP = {
    L_ROSE: LIVE,
    L_SUPERSEDED: ABSENT,
    L_WATCHER_GONE: ABSENT,
    L_NO_CHILD: ABSENT,
    L_FLAT: UNDETERMINED,
    L_ONE_SAMPLE: UNDETERMINED,
    L_NO_TABLE: UNDETERMINED,
    L_NO_PID: UNDETERMINED,
    L_CHILD_UNREADABLE: UNDETERMINED,
}

LIVENESS_TEXT = {
    L_ROSE: "a process under this watcher burned more CPU between two samples",
    L_FLAT: "two samples and no measurable rise - which is not death: a "
            "session waiting on an API burns no CPU",
    L_ONE_SAMPLE: "first sample in this process; load the page again for a "
                  "delta",
    L_SUPERSEDED: "the watcher has since logged a START for a later task, so "
                  "it has stopped listening for this one",
    L_WATCHER_GONE: "the pid file names a process that is not in the table",
    L_NO_CHILD: "the table was read and nothing is under this watcher",
    L_NO_TABLE: "the process table could not be read on this platform",
    L_NO_PID: "no file names this lane's watcher, so there is no root to walk",
    L_CHILD_UNREADABLE: "processes are there and none could be opened for a "
                        "CPU figure",
}

#: The two readings that make a deadline comparison unnecessary. Both are
#: statements that NOTHING WILL EVER FIRE: a watcher that is gone, and a
#: watcher that has moved on. Waiting for a deadline that cannot fire would
#: be the guess, not the caution - `qwen/0170` lost its supervisor 14 minutes
#: in and 75 minutes BEFORE its own deadline (`CONTINUITY.md` section 4 trap
#: 13: "timing points at ~01:13, not the deadline").
NOBODY_IS_LISTENING = (L_SUPERSEDED, L_WATCHER_GONE)


def _group(reading):
    if reading not in LIVENESS_GROUP:
        raise KeyError("liveness reading %r has no group; every reading is "
                       "classified explicitly" % (reading,))
    return LIVENESS_GROUP[reading]


def liveness(cpu=None, pid_state=None, table_read=None, superseded=None,
             watcher_alive=None):
    """Which of the nine readings holds, and which of the three it means.

    `cpu` is `src.lanes._cpu_reading`'s dict - handed in rather than
    recomputed, so a render that already walked the process table once does
    not walk it again and the board and this cell cannot disagree about what
    was under a watcher at a given instant.

    THE SUPERSESSION TEST COMES FIRST AND READS NO TABLE. It is the only
    liveness answer in this module that survives an unreadable process
    table, and it is the strongest one available: the watcher runs one task
    at a time, so a later START is the watcher saying in its own log that it
    is not listening for this dispatch any more. It also forecloses the
    error the obvious implementation makes - walking the watcher's children
    and finding THIS run's session, then reporting an abandoned dispatch
    from four hours ago as ALIVE. Measured on `webapp/0265`, which sat open
    from 16:10 while `0266`'s session ran under the same watcher pid.
    """
    reading = {"state": None, "group": None, "why": None,
               "seconds": None, "delta_seconds": None, "wall_seconds": None,
               "superseded_by": superseded}
    if superseded:
        reading["state"] = L_SUPERSEDED
    elif table_read is False:
        reading["state"] = L_NO_TABLE
    elif cpu is None:
        # No reading was handed in at all. Not an absence of processes.
        reading["state"] = L_NO_TABLE
    else:
        reading["seconds"] = cpu.get("seconds")
        reading["delta_seconds"] = cpu.get("delta_seconds")
        reading["wall_seconds"] = cpu.get("wall_seconds")
        count = cpu.get("count")
        if cpu.get("root_pid") is None:
            reading["state"] = L_NO_PID
        elif count is None:
            reading["state"] = L_NO_TABLE
        elif count == 0:
            # `_cpu_reading` reports count 0 both for a watcher that is in
            # the table with nothing under it and for a watcher that is not
            # in the table at all. They are different facts - the second
            # means the supervisor itself is gone - and they are told apart
            # by `watcher_alive`, which is the membership test itself.
            #
            # NOT BY THE `why` STRING `_cpu_reading` writes, which is what
            # the first draft of this did: a prose sniff for "not in the
            # table" would have kept answering correctly until somebody
            # reworded a comment, and this repository's own rule is to
            # assert on what a function returns rather than on its text.
            reading["state"] = (L_WATCHER_GONE if watcher_alive is False
                                else L_NO_CHILD)
        elif cpu.get("seconds") is None:
            reading["state"] = L_CHILD_UNREADABLE
        elif cpu.get("delta_seconds") is None:
            reading["state"] = L_ONE_SAMPLE
        elif cpu["delta_seconds"] > 0:
            reading["state"] = L_ROSE
        else:
            reading["state"] = L_FLAT
    reading["group"] = _group(reading["state"])
    reading["why"] = LIVENESS_TEXT[reading["state"]]
    reading["nobody_listening"] = reading["state"] in NOBODY_IS_LISTENING
    if pid_state is not None:
        reading["pid_state"] = pid_state
    return reading


# ------------------------------------------------------------- the deadline

#: Elapsed is past this lane's own cap.
D_PAST = "past_this_lane_s_own_deadline"
#: Elapsed is inside it.
D_WITHIN = "inside_this_lane_s_own_deadline"
#: No cap to compare against. `timeout_reading` names which of its three
#: reasons, and that state travels on the cell.
D_NO_TIMEOUT = "this_lane_s_timeout_is_unknown"
#: The START line could not be dated.
D_NO_ELAPSED = "the_start_could_not_be_dated"

DEADLINE_TEXT = {
    D_PAST: "past this lane's own deadline",
    D_WITHIN: "inside this lane's own deadline",
    D_NO_TIMEOUT: "this lane's own `watcher up` line carries no usable "
                  "timeout, so there is nothing to compare against",
    D_NO_ELAPSED: "this START line could not be dated, so no elapsed time "
                  "exists",
}


def deadline(elapsed_seconds, timeout_minutes):
    """`(state, over_seconds, remaining_seconds)`. A comparison needs both sides.

    Neither side is ever defaulted. The cap comes from this lane's own
    `watcher up` line and from nothing else - never the constant in
    `tools/lane_watcher.ps1` and never another lane's, because a running
    watcher keeps whatever constant it loaded with and `pilotcaps/0220`
    reported 150 against its own log's 90.
    """
    if elapsed_seconds is None:
        return D_NO_ELAPSED, None, None
    if timeout_minutes is None:
        return D_NO_TIMEOUT, None, None
    remaining = timeout_minutes * 60 - elapsed_seconds
    if remaining < 0:
        return D_PAST, -remaining, None
    return D_WITHIN, None, remaining


# ------------------------------------------------- did it run past its brief
#
# THE POSITIVE SIGNATURE OF TRAP 14, and the only leg here that reads the
# estate's own files. It is consulted ONLY where liveness is already proven,
# which bounds its cost to the handful of lanes that are actually working and
# keeps `webapp/0250`'s rule intact: a lane file's mtime may demote a row and
# never promote one, and the state this can reach is a refinement of ALIVE
# rather than any claim about landing.

#: Something naming a different id was written after this START.
P_FOUND = "found"
#: Both authorities were read and neither found anything.
P_NONE = "none_found"
#: Neither authority could be read.
P_UNREAD = "unread"
#: Not asked, because liveness was not proven. Distinct from "asked and
#: found nothing": an unasked question is not a negative answer.
P_NOT_ASKED = "not_asked"

PAST_TEXT = {
    P_FOUND: "something naming a DIFFERENT task id was written after this "
             "START",
    P_NONE: "both authorities were read since this START and neither names "
            "another task id",
    P_UNREAD: "neither authority could be read, so this question has no "
              "answer and the row stays plain ALIVE",
    P_NOT_ASKED: "not asked - liveness was not proven, and this question is "
                 "only a refinement of a proven ALIVE",
}

#: How far into the estate the artefact walk goes. Top level, plus one level
#: inside a directory whose own name carries a task id - which is what
#: catches `TASK-0399\\patch0399.py`, the measured suppression case, while a
#: recursive walk of a folder this size would not be a page read.
ARTEFACT_DEPTH = 1
#: A hard cap on entries examined, so an estate that grows cannot turn a page
#: render into a filesystem crawl. Reported when it bites, never silent.
MAX_ARTEFACT_ENTRIES = 6000
#: Folders never walked: the log folder changes every twenty seconds for
#: reasons that have nothing to do with a task, and the other two are not the
#: operator's files at all.
SKIP_DIRS = ("logs", ".git", "__pycache__", "queue", "runtime")
#: How much of a lane file's tail is read to find its newest heading. These
#: files reach a megabyte and are APPEND-ONLY, so the newest entry is at the
#: end; reading the whole file for one heading would cost 14 MB a render.
LANE_TAIL_BYTES = 128 * 1024

#: `TASK-0399`, `TASK-0397B`. Not lane-scoped by its name, so an id matched
#: this way is only attributed to a lane that has itself dispatched or queued
#: that id - otherwise `suppression`'s folder would be charged to `webapp`.
_TASK_DIR = re.compile(r"^TASK-0*(\d{1,4}[a-z]?)(?=[-._]|$)", re.I)


def _lane_prefix(lane):
    """`webapp-0270-entry.md` -> `0270`. The lane name is matched literally.

    Built per lane rather than as one pattern with a `[a-z-]+?` lane group,
    because lane names contain hyphens - `glm-b`, `qwen-coder` - and a lazy
    group would read `qwen-coder-0030` as lane `qwen` task `coder`.
    """
    return re.compile(r"^" + re.escape(lane) + r"-(\d{1,4}[a-z]?)(?=[-._]|$)",
                      re.I)


def _mtime(path):
    try:
        return datetime.datetime.fromtimestamp(os.path.getmtime(path))
    except OSError:
        return None


def lane_ids(events, queued=(), inflight=()):
    """Every task id this lane is known to have dispatched or to hold.

    The authority for attributing a `TASK-<id>` folder, which carries no lane
    in its name. An id this lane has never dispatched and does not hold is
    somebody else's folder, and charging it here would be the measurement on
    the wrong artifact - failure family four.
    """
    found = set()
    for event in events or ():
        task = event.get("task")
        if task:
            ident = _rework().brief_id(task)
            if ident:
                found.add(ident)
    for name in tuple(queued or ()) + tuple(inflight or ()):
        ident = _rework().brief_id(name)
        if ident:
            found.add(ident)
    return found


def artefact_writes(root, lane, task_id, start_when, known_ids=()):
    """Entries written after `start_when` whose name carries ANOTHER task id.

    `(writes, state)`. `state` is `P_UNREAD` when the estate root could not
    be listed at all - which is an absence of measurement and must not read
    as "nothing was written".
    """
    writes, examined, capped = [], 0, False
    try:
        entries = sorted(os.listdir(root))
    except OSError:
        return [], P_UNREAD, False
    pattern = _lane_prefix(lane)

    def consider(path, name, depth):
        """Name -> id -> mtime. The BASENAME only, never the whole path.

        A path search hands a scratch folder's own task number to every file
        under it, which is how `%TEMP%\\<lane>-<task>\\` once donated its
        dates to unrelated files.
        """
        match = pattern.match(name)
        ident = match.group(1) if match else None
        kind = "lane-named file"
        if ident is None:
            match = _TASK_DIR.match(name)
            if match and _rework().normalise_id(match.group(1)) in known_ids:
                ident, kind = match.group(1), "TASK folder this lane dispatched"
        if ident is None:
            return
        ident = _rework().normalise_id(ident)
        if ident == task_id:
            return
        when = _mtime(path)
        if when is None or when <= start_when:
            return
        writes.append({"kind": kind, "name": name, "task_id": ident,
                       "at": when.strftime("%Y-%m-%d %H:%M:%S"),
                       "when": when, "depth": depth})

    frontier = [(os.path.join(root, name), name, 0) for name in entries
                if name not in SKIP_DIRS]
    while frontier:
        if examined >= MAX_ARTEFACT_ENTRIES:
            capped = True
            break
        path, name, depth = frontier.pop(0)
        examined += 1
        consider(path, name, depth)
        if depth >= ARTEFACT_DEPTH or not os.path.isdir(path):
            continue
        # Only descend into a folder whose OWN name carries an id. A blind
        # one-level descent into every folder at the root would read several
        # thousand entries that cannot answer this question.
        if not (pattern.match(name) or _TASK_DIR.match(name)):
            continue
        try:
            for child in sorted(os.listdir(path)):
                frontier.append((os.path.join(path, child), child, depth + 1))
        except OSError:
            continue
    writes.sort(key=lambda row: row["when"], reverse=True)
    return writes, (P_FOUND if writes else P_NONE), capped


def lane_file_write(path, task_id, start_when):
    """The lane file's NEWEST heading, when the file was touched after `START`.

    `(write_or_None, state)`.

    TWO FACTS, AND NEITHER IS ENOUGH ALONE. The mtime says the file was
    written since the START and names no id; the newest heading names an id
    and carries no reliable clock. Crossed, and read against the fact that
    these files are APPENDED to and never rewritten, they say: the most
    recent thing written to this file is an entry about THAT id.

    STATED AS THE ASSUMPTION IT IS. An edit to an older section of the file
    would move the mtime without the newest heading being the thing written.
    That is why this leg can only ever refine an already-proven ALIVE into
    PAST BRIEF, and why no landing verdict anywhere reads it.
    """
    when = _mtime(path)
    if when is None:
        return None, P_UNREAD
    if when <= start_when:
        # Real evidence of absence, and the direction `CONTINUITY.md`
        # section 3 licenses the mtime for: an append-only file older than
        # the START was not appended to since it.
        return None, P_NONE
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as handle:
            handle.seek(max(0, size - LANE_TAIL_BYTES))
            raw = handle.read()
    except OSError:
        return None, P_UNREAD
    text = raw.decode("utf-8", errors="replace")
    if size > LANE_TAIL_BYTES:
        # The first line of a tail read may be half a line. Dropped rather
        # than parsed, because half a heading is not a heading.
        text = text.split("\n", 1)[1] if "\n" in text else ""
    found = _rework().headings(text)
    if not found:
        return None, P_UNREAD
    newest = found[-1]
    ids = [ident for ident in newest.get("task_ids") or ()
           if ident != task_id]
    if not ids:
        return None, P_NONE
    return ({"kind": "lane file's newest heading", "name": os.path.basename(path),
             "task_id": ids[0], "at": when.strftime("%Y-%m-%d %H:%M:%S"),
             "when": when, "heading": newest["text"][:160]}, P_FOUND)


def past_brief(root, lane, task_id, start_when, lane_file=None,
               known_ids=()):
    """Both authorities, crossed, with every unread one NAMED.

    Found by either is found. Unread by BOTH is `P_UNREAD`, and a row whose
    evidence is unread stays plain `OPEN_ALIVE` - the conservative direction,
    because PAST BRIEF is extra information about a lane that is already
    known to be working and its absence costs nothing but detail.
    """
    result = {"state": P_NONE, "writes": [], "unread": [], "capped": False}
    if task_id is None:
        result["state"] = P_UNREAD
        result["unread"] = ["the START's filename carries no task id"]
        return result
    writes, state, capped = artefact_writes(root, lane, task_id, start_when,
                                            known_ids)
    result["capped"] = capped
    if state == P_UNREAD:
        result["unread"].append("the estate root could not be listed")
    else:
        result["writes"].extend(writes)
    lane_file = lane_file or os.path.join(root, "LANE-%s.md" % lane)
    write, lane_state = lane_file_write(lane_file, task_id, start_when)
    if lane_state == P_UNREAD:
        result["unread"].append("%s could not be read"
                                % os.path.basename(lane_file))
    elif write is not None:
        result["writes"].append(write)
    if result["writes"]:
        result["state"] = P_FOUND
    elif len(result["unread"]) == 2:
        result["state"] = P_UNREAD
    result["writes"].sort(key=lambda row: row["when"], reverse=True)
    return result


# ------------------------------------------------------------ the classifier


def classify(live, past, deadline_state):
    """The five verdicts, in one ordered pass. No branch reaches two of them.

    THE ORDER IS THE DESIGN and each step earns its place:

    1. UNDETERMINED first, because an unmeasurable liveness must not be
       allowed to fall through into a deadline comparison and come out as a
       confident WITHIN - which is the quiet version of reporting clean.
    2. ALIVE next, split by the past-brief evidence. Both are healthy; the
       split exists so trap 14's unconsumed brief is visible before the
       session ends rather than after.
    3. The absences last, and the deadline only binds the WEAKEST of them.
       A watcher that is gone or has moved on will never fire a timeout, so
       waiting for one is not caution. Where the deadline is needed and
       cannot be computed the answer is UNDETERMINED, never WITHIN.
    """
    if live["group"] == UNDETERMINED:
        return OPEN_UNDETERMINED
    if live["group"] == LIVE:
        return (OPEN_PAST_BRIEF if past and past["state"] == P_FOUND
                else OPEN_ALIVE)
    if live.get("nobody_listening"):
        return OPEN_NO_LIVENESS
    if deadline_state == D_PAST:
        return OPEN_NO_LIVENESS
    if deadline_state == D_WITHIN:
        return OPEN_WITHIN_DEADLINE
    return OPEN_UNDETERMINED


# --------------------------------------------------------------- the records


def dispatches(events):
    """Every START, with the coded ending that closed it, in log order.

    THE ENDING IS THE WATCHER'S OWN `DONE` LINE AND NOTHING ELSE. Not the
    `DONE/` filename, which is positively false for nine entries stamped
    `20261016-0042`-`0145`; not an empty `RUNNING/`, which `webapp/0265` had
    while its dispatch was still open; not the `.out`.

    A `DONE` is matched to the newest unclosed START FOR THE SAME TASK. A
    lane can hold more than one open START at once - `glm` holds two from
    2026-10-15 - and pairing by position alone would close the wrong one.
    """
    rows, open_by_task = [], {}
    for event in events or ():
        if event["kind"] == "start":
            row = {"task": event["task"],
                   "task_id": _rework().brief_id(event["task"]),
                   "at": event["at"], "when": event["when"],
                   "line": event["line"], "ending": None, "ending_at": None,
                   "ending_line": None, "superseded_by": None,
                   "superseded_at": None}
            # Every START that is still open is superseded by this one: the
            # watcher runs one task at a time, so dispatching this is the
            # watcher saying it is not listening for those any more.
            for earlier in rows:
                if earlier["ending"] is None and earlier is not row \
                        and earlier["superseded_by"] is None:
                    earlier["superseded_by"] = event["task"]
                    earlier["superseded_at"] = event["at"]
            rows.append(row)
            open_by_task[event["task"]] = row
        elif event["kind"] == "done":
            row = open_by_task.pop(event["task"], None)
            if row is not None:
                row["ending"] = event.get("suffix")
                row["ending_at"] = event["at"]
                row["ending_line"] = event["line"]
    return rows


def cell(root, lane, events, timeout, now, cpu=None, pid_state=None,
         table_read=None, watcher_alive=None, queued=(), inflight=(),
         read_past=True, lane_file=None):
    """This lane's open dispatches, each with one of the five verdicts.

    `timeout` is `src.lanes.timeout_reading(events)` - handed in, so there
    is exactly one implementation of the rule that the cap comes from this
    lane's own `watcher up` line, and so the cell can print the line it came
    from. `cpu` is `src.lanes._cpu_reading`'s dict for the same render.

    `read_past=False` turns off the only leg that touches the filesystem,
    for a caller that wants the verdict without the estate walk. The rows
    then say `P_NOT_ASKED` rather than reporting no evidence found.
    """
    rows = dispatches(events)
    open_rows = [row for row in rows if row["ending"] is None]
    known = lane_ids(events, queued, inflight)
    out = []
    for row in open_rows:
        elapsed = None
        if row["when"] is not None:
            elapsed = int(round((now - row["when"]).total_seconds()))
            if elapsed < 0:
                # A START stamped in the future. Not negative time: an
                # undated elapsed, which the deadline refuses to compare.
                elapsed = None
        live = liveness(cpu=cpu, pid_state=pid_state, table_read=table_read,
                        superseded=row["superseded_by"],
                        watcher_alive=watcher_alive)
        state, over, remaining = deadline(elapsed, timeout.get("minutes"))
        past = {"state": P_NOT_ASKED, "writes": [], "unread": [],
                "capped": False}
        if read_past and live["group"] == LIVE:
            past = past_brief(root, lane, row["task_id"], row["when"],
                              lane_file=lane_file, known_ids=known)
        verdict = classify(live, past, state)
        label, why = OPEN_TEXT[verdict]
        out.append({
            "lane": lane,
            "task": row["task"],
            "task_id": row["task_id"],
            "start_at": row["at"],
            "start_line": row["line"],
            "elapsed_seconds": elapsed,
            "superseded_by": row["superseded_by"],
            "superseded_at": row["superseded_at"],
            "liveness": live,
            "deadline_state": state,
            "deadline_why": DEADLINE_TEXT[state],
            "over_seconds": over,
            "remaining_seconds": remaining,
            "past": past,
            "past_why": PAST_TEXT[past["state"]],
            "verdict": verdict,
            "label": label,
            "why": why,
            "what_to_do": WHAT_TO_DO[verdict],
        })
    out.sort(key=lambda row: row["start_at"], reverse=True)
    worst = None
    for verdict in OPEN_ORDER:
        if any(row["verdict"] == verdict for row in out):
            worst = verdict
            break
    return {
        "lane": lane,
        "open": out,
        "open_count": len(out),
        # Dispatches that DID take a coded exit. Carried so a reader can see
        # the denominator the open ones came out of, and so that a cell with
        # a real TIMEOUT in its history is visibly not an absence of records.
        "closed_count": len(rows) - len(out),
        "endings": sorted({row["ending"] for row in rows
                           if row["ending"] is not None}),
        "verdict": worst,
        "label": OPEN_TEXT[worst][0] if worst else None,
        # THE TIMEOUT AUTHORITY, AND THE LINE IT WAS READ FROM. Printed on
        # every cell, because a cap with no provenance is the figure
        # `pilotcaps/0220` got wrong by 60 minutes.
        "timeout_minutes": timeout.get("minutes"),
        "timeout_state": timeout.get("state"),
        "timeout_from_line": timeout.get("from_line"),
        "timeout_from_at": timeout.get("from_at"),
    }


# ------------------------------------------------------------- the controls
#
# C6 OF TASK 0266: the board does not print this column unless C1, C2 and C4
# have all been OBSERVED on the rows about to be rendered. A classifier that
# can only ever reach one answer is not a classifier, and the one this estate
# keeps needing is C4 - an instrument that cannot report its own blindness
# reports clean.
#
# COMPUTED HERE AND NOT IN A TEMPLATE, for the same reason `webapp/0250` gave
# for its clock controls: a template that could decide this could also decide
# to skip it.

#: Each control: the name, what it needs to see, and why.
CONTROL_TEXT = {
    "C1": ("an ALIVE row is reachable",
           "a row whose liveness group is ALIVE, proving the cell can say "
           "somebody is listening"),
    "C2": ("a NO LIVENESS row is reachable",
           "a row whose verdict is OPEN, NO LIVENESS, proving the cell can "
           "say nobody is"),
    "C4": ("UNDETERMINED is reachable",
           "a row whose verdict is UNDETERMINED, proving the cell reports "
           "its own blindness rather than guessing"),
}


def controls(cells, probe_blind=None):
    """`[{name, ok, label, why, seen}]` over the cells about to be rendered.

    `probe_blind` is the UNDETERMINED leg measured directly rather than
    waited for: a caller hands in the verdict a DELIBERATELY BLINDED probe
    produced, so C4 is observed on every render instead of only on the
    renders where something happened to be unmeasurable. A control that is
    only satisfied by luck is not a control.
    """
    rows = [row for data in (cells or ()) for row in data.get("open", ())]
    seen = {
        "C1": [row["task"] for row in rows
               if row["liveness"]["group"] == LIVE],
        "C2": [row["task"] for row in rows
               if row["verdict"] == OPEN_NO_LIVENESS],
        "C4": [row["task"] for row in rows
               if row["verdict"] == OPEN_UNDETERMINED],
    }
    if probe_blind == OPEN_UNDETERMINED:
        seen["C4"] = seen["C4"] + ["<blinded probe>"]
    out = []
    for name in ("C1", "C2", "C4"):
        label, why = CONTROL_TEXT[name]
        out.append({"name": name, "label": label, "why": why,
                    "seen": seen[name], "ok": bool(seen[name])})
    return out


def blind_probe_verdict(now=None):
    """What this cell says when the process table cannot be read at all.

    THE C4 MEASUREMENT, taken rather than hoped for. One synthetic dispatch,
    one log line, and a liveness reading whose table is unreadable. If this
    ever returns anything but `OPEN_UNDETERMINED` the column is refused,
    because the state the whole module exists to protect - an unmeasurable
    liveness that does not collapse into a guess - would be gone.
    """
    now = now or datetime.datetime.now()
    start = now - datetime.timedelta(hours=9)
    events = [{"kind": "up", "at": "", "when": start, "timeout_minutes": 150,
               "line": "[] [x] watcher up. timeout=150m"},
              {"kind": "start", "at": start.strftime("%Y-%m-%d %H:%M:%S"),
               "when": start, "task": "0001-blinded-probe.md",
               "line": "[] [x] START 0001-blinded-probe.md"}]
    data = cell(root=None, lane="<blinded probe>", events=events,
                timeout={"minutes": 150, "state": "in_force",
                         "from_line": None, "from_at": None},
                now=now, cpu=None, table_read=False, read_past=False)
    return data["verdict"]


def describe(data=None):
    """What this cell is, in the words the page prints. No numbers invented."""
    return {
        "verdicts": [{"verdict": verdict, "label": OPEN_TEXT[verdict][0],
                      "why": OPEN_TEXT[verdict][1],
                      "what_to_do": WHAT_TO_DO[verdict]}
                     for verdict in OPEN_ORDER],
        "liveness": [{"state": state, "group": LIVENESS_GROUP[state],
                      "why": LIVENESS_TEXT[state]}
                     for state in LIVENESS_GROUP],
        "deadline": [{"state": state, "why": why}
                     for state, why in DEADLINE_TEXT.items()],
        "past": [{"state": state, "why": why}
                 for state, why in PAST_TEXT.items()],
        "authorities": [
            ("the watcher's own log",
             "whether this dispatch has a coded ending, and whether a LATER "
             "START exists. Needs no process table"),
            ("the process table",
             "whether a child of this lane's watcher burned CPU between two "
             "samples. A read, never a signal"),
            ("the estate's own files",
             "whether something naming a DIFFERENT task id was written since "
             "the START. Consulted only where liveness is already proven"),
        ],
    }
