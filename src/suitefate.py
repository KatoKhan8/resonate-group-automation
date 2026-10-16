"""Did the session that launched a suite ever learn what it said?

THE STATE THIS ESTATE HAD NO NAME FOR, AND IT IS NOT THE LOCK'S.
`src.lanes` already names ORPHAN: a lock file whose holder is dead. That is a
fact about a LOCK. This module names a different one - DIED-UNREAD: the
session that launched a suite closed without the result. Measured twice
inside ninety minutes on 2026-10-16, in opposite directions:

    pilotcaps/0234b  launched at 06:16:47, closed 06:20:08 saying "I'll wait
                     for its completion notification". There is no
                     notification. The suite died four minutes in and its
                     lock is STILL stranded.
    suppression/0220 launched pid 79556 at 04:44, closed 04:45:37 - 81
                     seconds later. The run finished at 05:35:20.7 and
                     RELEASED ITS LOCK CLEANLY. Two sessions had come and
                     gone before the result existed.

THE TWO AXES ARE INDEPENDENT AND MUST NOT BE COLLAPSED. The first case is
DIED-UNREAD *with* a stranded lock; the second is DIED-UNREAD *without* one.
A lock can be stranded by a run whose launcher did learn the outcome (it read
the log, then the machine died), and a launcher can be left ignorant by a run
that released its lock perfectly. So every launch here carries a FATE and,
beside it, a LOCK DISPOSITION, and neither is derived from the other.

WHAT COUNTS AS EVIDENCE OF A LAUNCH. Two routes, both structural, because the
obvious third one does not work:

  THE LOCK ROUTE. `suitelock.acquire` writes `pid`, `started_at` and
  `worktree` into the lock file. The worktree names the LANE and `started_at`
  is a stamp the lock itself wrote, so neither can be clobbered by somebody
  copying a file. This is the only route that can see a run which produced no
  verdict at all - and a STRANDED lock proves exactly that, because
  `scripts/run_suite.py` calls `release()` in a `finally`, so a lock still
  present with a dead holder proves the process was killed before the
  `finally` ran and therefore before `VERDICT_FILE` was written.

  THE VERDICT ROUTE. `build_verdict` writes `log_file=`, which is
  `PROJECT_ROOT` - the tree the suite ran in, written by the runner itself
  rather than by prose. That gives the LANE. The launching SESSION then comes
  from a pid: `pid<N>` in the artefact's filename, joined to the earliest
  `.out` of that lane whose text names the same pid.

  THE ROUTE THAT DOES NOT WORK, and it was measured before it was rejected.
  Scanning every `task-<lane>-<stamp>.out` for a pid inside a sentence about a
  suite returns 11 hits, and MOST OF THEM ARE OBSERVERS rather than launchers:
  `pilotcaps/20261015-040306` names pid 79120 to report that somebody else's
  lock is stranded, and `webapp/20261016-054427` names 79556 to report the
  same about the run `suppression/0220` had launched. Attributing a launch to
  whoever mentions its pid would have charged four sessions with one launch
  and named the wrong lane for two of them. Prose is kept, but only in the
  role it can actually carry: CORROBORATION that a session recorded a result.

WHY A TIME IS NOT ALWAYS A TIME. `build_verdict` records no timestamp, no pid
and no SHA (`suppression/0280`'s finding), so the only clock a verdict carries
is its own mtime - and an mtime is destroyed the instant anybody copies the
file. Measured here: of 20 distinct verdicts under `logs/`, 16 exist as two or
more byte-identical copies at different mtimes, and one of them is the
`suppression/0220` run itself, whose four copies sit at 05:57:47, 06:24:16 and
twice at 08:05:53 - none of which is its real 05:35:20.7. So a launch whose
mtime is contradicted by an identical copy is marked CLOBBERED and is NEVER
given a session by time. It gets one by pid or it gets none.

WHAT THIS REFUSES TO DO. It writes nothing, clears no lock, signals no
process, and reads no lane's worktree - only `logs/`, the watcher logs, and
the one machine-wide lock. It does not call `suitelock._live_tickets`, which
deletes a dead owner's ticket as it walks.
"""

import datetime
import hashlib
import os
import re

from src import lanes
from src import suitelock


# --------------------------------------------------------------- the fates
#
# Prefixed `fate_` so this fourth vocabulary cannot collide with the verdict,
# outcome or lock ones in `src.lanes`.

#: The launching session was still open when the result existed AND its own
#: record names it. The only state that means a suite was actually consumed.
FATE_FINISHED_READ = "fate_finished_read"
#: THE NEW ONE. The launching session closed before the result existed - or
#: before any result existed at all, because the run was killed. Whatever the
#: suite said, nobody in the session that asked the question ever heard it.
FATE_DIED_UNREAD = "fate_died_unread"
#: The launcher was still open when the result landed and nothing in its
#: record names it. Deliberately NOT died-unread (it could have read it) and
#: NOT finished-read (nothing says it did): calling it either way is the
#: nearest-available-name defect this module exists to avoid.
FATE_LANDED_UNRECORDED = "fate_landed_unrecorded"
#: The launching session has not closed yet, so its fate is not yet decided.
#: Never counted as read and never counted as unread.
FATE_RUNNING = "fate_running"
#: The launch could not be tied to a lane session, or its result could not be
#: established. NEVER rendered as read: an untraceable launch is the hole in
#: the instrument, not a success.
FATE_UNKNOWN = "fate_unknown"

#: What each fate means and what it does NOT license. The words travel with
#: the data, so no page holds a table of its own - the convention
#: `lanes.VERDICT_TEXT` and `lanes.LOCK_TEXT` already set.
FATE_TEXT = {
    FATE_FINISHED_READ: (
        "RESULT READ",
        "the suite finished while the session that launched it was still "
        "open, and that session's own record names the result. This is the "
        "only state in which a suite's answer reached the person who asked "
        "the question"),
    FATE_DIED_UNREAD: (
        "DIED UNREAD",
        "the session that launched this suite closed before the result "
        "existed - either because the run was still going, or because it was "
        "killed and never wrote one. Nothing re-invokes a closed session, so "
        "the suite time was spent and its answer was never heard. This is "
        "NOT the same question as whether the lock was left stranded"),
    FATE_LANDED_UNRECORDED: (
        "LANDED, NO RECORD",
        "the result existed before the launching session closed, so it COULD "
        "have been read, and nothing in that session's record names it. Not "
        "counted as read, because a result nobody wrote down is not a result "
        "anybody acted on - and not counted as died-unread, because the "
        "session had the chance"),
    FATE_RUNNING: (
        "STILL OPEN",
        "the session that launched this suite has not closed yet, so whether "
        "it learns the outcome is not yet decided. It is counted in no "
        "numerator and in no denominator of read-versus-unread"),
    FATE_UNKNOWN: (
        "UNKNOWN",
        "this launch could not be tied to a lane session, or its result "
        "could not be established from anything readable here. An "
        "untraceable launch is a hole in this instrument and is never "
        "reported as a result somebody read"),
}

#: The fates that are decided and count against a denominator. RUNNING and
#: UNKNOWN are excluded by construction: one is undecided and one is the
#: instrument failing, and folding either into a rate would flatter it.
DECIDED = (FATE_FINISHED_READ, FATE_DIED_UNREAD, FATE_LANDED_UNRECORDED)


# ------------------------------------------- the lock, as a SEPARATE answer

#: A lock file names this launch's pid and the holder is dead. Nothing will
#: release it. `lanes.LOCK_ORPHAN` is the same fact seen from the lock's side;
#: this is it seen from the launch's.
LOCKD_STRANDED = "lockd_stranded"
#: A lock file names this launch's pid and the holder is in the process table.
LOCKD_LIVE = "lockd_live"
#: The lock authority was read and names some OTHER pid, or no lock is there
#: at all. This launch's `release()` ran. The clean-release half of the proof
#: that fate and lock are independent.
LOCKD_RELEASED = "lockd_released"
#: No pid is known for this launch, or the lock authority could not be
#: consulted. Never rendered as released.
LOCKD_UNDETERMINED = "lockd_undetermined"

LOCKD_TEXT = {
    LOCKD_STRANDED: (
        "LOCK STRANDED",
        "a lock file still names this run's pid and that pid is not in the "
        "process table. `run_suite` releases the lock in a `finally`, so a "
        "lock still present with a dead holder proves the process was killed "
        "before it could write a verdict"),
    LOCKD_LIVE: (
        "LOCK HELD",
        "a lock file names this run's pid and the holder is in the process "
        "table, so this suite is still running and every other run waits"),
    LOCKD_RELEASED: (
        "LOCK RELEASED",
        "the lock authority was consulted and does not name this run's pid, "
        "so this run released it. A clean release says NOTHING about whether "
        "anybody read the result - `suppression/0220` released perfectly and "
        "its answer went unread for thirty minutes"),
    LOCKD_UNDETERMINED: (
        "LOCK UNDETERMINED",
        "this launch has no pid this reader could establish, or the lock "
        "authority could not be consulted. Not released, and not stranded"),
}


# --------------------------------------------- where a launch's clock came from

#: Written by `suitelock.acquire` into the lock payload. Authoritative: no
#: file copy can move it, because it is CONTENT rather than metadata.
TIME_LOCK = "lock_started_at"
#: An artefact's mtime, and this reader found no byte-identical copy
#: elsewhere, so nothing contradicts it being the write time.
TIME_MTIME = "artefact_mtime"
#: An artefact's mtime, CONTRADICTED by a byte-identical copy at a different
#: mtime. At most one of them can be the write time and nothing here says
#: which, so the clock is not used to attribute a session.
TIME_CLOBBERED = "artefact_mtime_clobbered"
#: No clock at all.
TIME_NONE = "no_clock"

TIME_TEXT = {
    TIME_LOCK: ("from the lock's own stamp",
                "`suitelock.acquire` wrote `started_at` into the lock file as "
                "content, so copying a file cannot move it"),
    TIME_MTIME: ("from the artefact's mtime",
                 "no byte-identical copy of this artefact was found "
                 "elsewhere, so nothing contradicts its mtime being the time "
                 "it was written"),
    TIME_CLOBBERED: ("mtime CONTRADICTED by a copy",
                     "a byte-identical copy of this artefact exists at a "
                     "different mtime, so at most one of them is the write "
                     "time and nothing here says which. This clock is not "
                     "used to attribute a session"),
    TIME_NONE: ("no clock",
                "nothing readable here dates this launch"),
}


#: `task-<lane>-<YYYYmmdd>-<HHMMSS>.out`. The watcher builds this filename and
#: the DONE entry from one `$stamp`, so the stamp is an authority for the join
#: rather than an inference from a clock - `lanes.join_out`'s point, reused.
_OUT_NAME = re.compile(r"^task-(.+)-(\d{8}-\d{6})\.out$")
_OUT_STAMP = "%Y%m%d-%H%M%S"

#: `pid79556` or `pid-79556` inside an artefact's filename. The one piece of
#: identity any verdict in this estate carries, and it is there because a lane
#: put it there by hand - `build_verdict` cannot write one.
_PID_IN_NAME = re.compile(r"pid[-_]?(\d{3,7})")

#: A run_suite verdict. All five keys, because a file with `status=` alone
#: could be anything; `wall_seconds` and `exit_code` together are this
#: format's signature.
_VERDICT_KEY = re.compile(r"^(\w+)=(.*)$", re.M)
_VERDICT_REQUIRED = ("status", "exit_code", "wall_seconds")

#: How far into a file to look for the verdict header.
_HEAD_BYTES = 8192

#: A `.out` is the session's FINAL answer only - the watcher writes it when
#: `claude -p` exits - so it is exactly the right place to ask whether the
#: session recorded a result, and the wrong place to ask what it did at
#: minute three.
MAX_OUT_BYTES = 256 * 1024

#: Cap on the artefact walk, so a page request cannot be made to hash a tree
#: of arbitrary size. Exceeding it is REPORTED, never silently truncated.
MAX_ARTEFACTS = 20000


def _lane_trees(root):
    """`{absolute tree path: lane}`, read from each watcher's own `up` line.

    THE MAPPING IS NEVER HARDCODED. The watcher announces
    `worktree=<path>` (or `tree=<path>` for the two lanes that are not
    worktrees) on the line it writes at start-up, so that line is the one
    authority for which tree belongs to which lane. A table in this file
    would be a second representation of it, and the two would drift the
    first time a lane moved.
    """
    found = {}
    for lane, _where in lanes.lane_names(root):
        path = os.path.join(root, "logs", "watcher-%s.log" % lane)
        state, lines, _trunc = lanes._read_tail(path)
        if state != lanes.PRESENT:
            continue
        for line in lines:
            match = re.search(r"\b(?:worktree|tree)=(.+?)\s+mode=", line)
            if match:
                found[os.path.normcase(os.path.abspath(match.group(1)))] = lane
    return found


def _lane_of_tree(path, trees):
    """Which lane's tree does this `log_file=` sit in? None when no lane's.

    `log_file` is `<tree>/scripts/suite_run.log`, so the tree is a PREFIX of
    it. An ad-hoc reference tree (`resonate-ops/ref-cd8e00bc`) and a Claude
    session scratch directory under `Temp` belong to no lane and must come
    back None rather than being matched to whichever lane sorts first.
    """
    if not path:
        return None
    norm = os.path.normcase(os.path.abspath(path))
    for tree, lane in sorted(trees.items(), key=lambda kv: -len(kv[0])):
        if norm == tree or norm.startswith(tree + os.sep):
            return lane
    return None


def sessions(root, lane):
    """`[{brief, start, done, suffix}]` for one lane, newest last.

    THE AUTHORITY FOR A SESSION CLOSING IS THE `DONE ... exit0` LINE, never a
    filename in `DONE/` and never a non-empty `.out` - `qwen/0130` measured a
    `DONE/` folder count overstating finished work by 44%. A START with no
    DONE after it is a session that has not closed, and its `done` is None,
    which is the whole reason a fate can be RUNNING rather than unread.
    """
    path = os.path.join(root, "logs", "watcher-%s.log" % lane)
    state, lines, truncated = lanes._read_tail(path)
    if state != lanes.PRESENT:
        return None, state, truncated
    events = lanes.watcher_events(lines, lane)
    open_rows, closed = [], []
    for event in events:
        if event["kind"] == "start":
            open_rows.append({"brief": event["task"], "start": event["when"],
                              "done": None, "suffix": None,
                              "done_line": None})
        elif event["kind"] == "done":
            # Close the newest open START. The watcher is strictly serial per
            # lane - it dispatches the next file only when `claude -p` exits -
            # so there is never more than one open at a time, and pairing
            # newest-first is right even when a DONE names a different brief
            # than the START did.
            for row in reversed(open_rows):
                if row["done"] is None:
                    row["done"] = event["when"]
                    row["suffix"] = event["suffix"]
                    row["done_line"] = event["line"]
                    break
            else:
                # A DONE with no START before it. The log's tail was cut, or
                # the watcher restarted mid-task. Recorded rather than
                # dropped: a closed session whose start is unknown still
                # proves something closed.
                closed.append({"brief": event["task"], "start": None,
                               "done": event["when"],
                               "suffix": event["suffix"],
                               "done_line": event["line"]})
    rows = sorted(open_rows + closed,
                  key=lambda r: (r["start"] or r["done"] or
                                 datetime.datetime.min))
    return rows, state, truncated


def _session_at(rows, when):
    """The session open at `when`, or None. Never the nearest one.

    A launch that falls in a GAP between two sessions belongs to neither. The
    watcher leaves a five-second gap between a DONE and the next START, and a
    launch landing in one is not the next session's work.

    NEWEST-FIRST, AND THAT IS NOT A STYLE CHOICE. Measured 2026-10-16: the
    pilotcaps log holds `0130-certify-the-halt-fix.md`, STARTed at 10-15
    16:02:10 and never closed by a DONE line - a watcher generation boundary.
    Walking oldest-first, every launch for the following sixteen hours
    matched that stale open START first and was attributed to it, so the
    0234b instance this module exists for came back STILL OPEN. A session
    with no DONE swallows everything after it unless the newest candidate
    wins, and the newest is also the only correct answer: the watcher is
    strictly serial per lane, so at any instant the open session is the one
    with the greatest START at or before it.
    """
    if rows is None or when is None:
        return None
    for row in reversed(rows):
        if row["start"] is None or row["start"] > when:
            continue
        if row["done"] is None or row["done"] >= when:
            return row
        # The newest START at or before `when` closed BEFORE `when`, so
        # nothing was open: the launch fell in a gap. Returning an older
        # session here would be the nearest-available-name defect again.
        return None
    return None


def out_records(root, lane):
    """`[{stamp, start, path, text}]` for one lane's `.out` files, oldest first.

    None when the directory could not be listed - which is not "this lane
    wrote no output", exactly as `lanes.out_files` refuses with None rather
    than `{}`.
    """
    logs_dir = os.path.join(root, "logs")
    try:
        names = sorted(os.listdir(logs_dir))
    except OSError:
        return None
    rows = []
    for name in names:
        match = _OUT_NAME.match(name)
        if not match or match.group(1) != lane:
            continue
        stamp = match.group(2)
        try:
            when = datetime.datetime.strptime(stamp, _OUT_STAMP)
        except ValueError:
            when = None
        path = os.path.join(logs_dir, name)
        try:
            with open(path, "rb") as handle:
                blob = handle.read(MAX_OUT_BYTES)
        except OSError:
            # Present and unreadable. The row is kept with text None so a
            # corroboration search cannot read it as "the session said
            # nothing" - an unreadable record is UNKNOWN, not silence.
            rows.append({"stamp": stamp, "start": when, "path": path,
                         "name": name, "text": None})
            continue
        rows.append({"stamp": stamp, "start": when, "path": path,
                     "name": name,
                     "text": blob.decode("utf-8", "replace")})
    return sorted(rows, key=lambda r: r["stamp"])


def artefacts(root):
    """Every run_suite verdict under `logs/`, grouped by CONTENT.

    `(groups, walked, capped)`. One group per distinct md5, carrying every
    path that holds those bytes and the earliest mtime among them. Grouping by
    content rather than by path is what makes the copy hazard visible at all:
    `suppression/0280` reproduced two runs sharing one log, and a lane
    collecting artefacts re-stamped seventeen verdicts in three seconds on the
    morning this was written.
    """
    logs_dir = os.path.join(root, "logs")
    groups, walked, capped = {}, 0, False
    for dirpath, dirnames, filenames in os.walk(logs_dir):
        dirnames.sort()
        for name in sorted(filenames):
            if walked >= MAX_ARTEFACTS:
                capped = True
                break
            path = os.path.join(dirpath, name)
            walked += 1
            try:
                with open(path, "rb") as handle:
                    head = handle.read(_HEAD_BYTES)
            except OSError:
                continue
            fields = dict(_VERDICT_KEY.findall(
                head.decode("utf-8", "replace")))
            if not all(key in fields for key in _VERDICT_REQUIRED):
                continue
            try:
                with open(path, "rb") as handle:
                    blob = handle.read()
                stat = os.stat(path)
            except OSError:
                continue
            md5 = hashlib.md5(blob).hexdigest()
            group = groups.setdefault(md5, {
                "md5": md5, "fields": fields, "copies": [],
            })
            group["copies"].append({
                "path": path,
                "rel": os.path.relpath(path, logs_dir).replace(os.sep, "/"),
                "name": name,
                "mtime": datetime.datetime.fromtimestamp(stat.st_mtime),
            })
        if capped:
            break
    for group in groups.values():
        group["copies"].sort(key=lambda c: c["mtime"])
        stamps = {c["mtime"] for c in group["copies"]}
        group["earliest"] = group["copies"][0]["mtime"]
        # THE TEST FOR A CLOBBERED CLOCK. Two byte-identical files cannot
        # both have been written at two different times, so a disagreement
        # proves at least one mtime is a copy time. One copy, or several that
        # agree, leaves the mtime uncontradicted.
        group["clobbered"] = len(stamps) > 1
        group["pid"] = None
        for copy in group["copies"]:
            match = _PID_IN_NAME.search(copy["name"])
            if match:
                group["pid"] = int(match.group(1))
                break
    return groups, walked, capped


def _wall_seconds(fields):
    """`wall_seconds` as a float, or None. A missing one is never a zero."""
    try:
        return float(fields.get("wall_seconds"))
    except (TypeError, ValueError):
        return None


def lock_launches(file_path=None, probe=None, table=None):
    """The machine-wide lock as a launch, when it names a usable holder.

    A list of at most one today, for the same reason `lanes.locks` returns a
    list of one: a second machine-wide lock should arrive as another row
    rather than as a rewrite of this function.

    This is the ONLY route that can see a run which wrote no verdict, and it
    is the route that carries the uncopyable clock.
    """
    probe = probe or lanes.SystemProbe()
    if table is None:
        table = probe.table()
    try:
        path = file_path or suitelock.path()
    except Exception:
        return [], None
    holder = suitelock.read(path)
    if not isinstance(holder, dict) or holder.get("damaged"):
        return [], path
    pid = holder.get("pid")
    if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
        return [], path
    try:
        started = datetime.datetime.strptime(
            str(holder.get("started_at")), lanes.LOCK_STAMP)
    except (TypeError, ValueError):
        started = None
    alive = None
    if table is not None:
        alive = pid in table
    return [{
        "pid": pid,
        "worktree": holder.get("worktree"),
        "branch": holder.get("branch"),
        "launch_at": started,
        "launch_clock": TIME_LOCK if started else TIME_NONE,
        "alive": alive,
        "lock_path": path,
    }], path


def _recorded(text, group, result_at):
    """Does this session's own record name the suite's result? `(bool, how)`.

    CORROBORATION HAS TO BE SPECIFIC OR IT IS NOTHING. "The word suite
    appears" would make every session in this estate a reader. Three markers,
    each of which a session can only write by having looked at the result:

      * the artefact's own filename, which a session that filed the result
        names when it says where it put it;
      * the verdict's `failures=` count, which only the verdict carries;
      * the result's clock to the minute, which only something that watched
        it land can state.

    An unreadable `.out` returns `(None, ...)` - UNKNOWN, never False, because
    absence of a record this reader could not open is not absence of a record.
    """
    if text is None:
        return None, "this session's output could not be read"
    hits = []
    for copy in group["copies"]:
        stem = os.path.splitext(copy["name"])[0]
        if len(stem) >= 12 and stem in text:
            hits.append("names the artefact %s" % copy["name"])
            break
    failures = group["fields"].get("failures")
    if failures and failures.isdigit() and int(failures) > 2:
        # A failures count of 0, 1 or 2 is too common a number in prose to
        # carry any weight. Above that it is this verdict's signature.
        if re.search(r"\b%s\b" % re.escape(failures), text):
            hits.append("quotes the verdict's failures=%s" % failures)
    if result_at is not None:
        clock = result_at.strftime("%H:%M")
        if clock in text:
            hits.append("states the landing time %s" % clock)
    return bool(hits), "; ".join(hits) if hits else (
        "nothing in this session's record names this result")


#: How a launch was tied to its session. The arithmetic route below is only
#: available for `BY_PID`, because only an announcement proves the launch
#: happened INSIDE the session's own window.
BY_PID = "pid_announcement"
BY_TIME = "derived_launch_time"
BY_LOCK = "lock_worktree_and_stamp"


def _classify(launcher, attributed_by, result_upper, result_exact, wall,
              recorded):
    """`(fate, why)`. The whole decision, in one place, read by one caller.

    ONE RULE, ONE READER. `webapp/0140`'s M1 lesson was a second inline copy
    of a rule leaving every control green, so this is the only place a fate is
    decided and `launches` is the only caller.

    THE TWO CLOCKS ARE NOT THE SAME KIND OF FACT, and keeping them apart is
    what stops this instrument from charging a session with abandoning a
    result it may well have read.

      `result_exact` is a write time nothing contradicts. It settles the
      comparison in both directions.

      `result_upper` is the earliest mtime among byte-identical copies, which
      is an UPPER BOUND on the write time and nothing more - the original can
      have been overwritten and every surviving file be a copy, which is
      exactly what happened to the `suppression/0220` run. An upper bound can
      prove a result EXISTED EARLY ENOUGH (`done >= upper` implies `done >=
      true`), and can never prove one landed late.

      `wall` plus an announcement needs no mtime at all, and it is the
      strongest route here. If a session announced the launch, the run began
      inside that session's own window, so the result cannot predate
      `start + wall`. When `start + wall` is already past `done`, the run
      PROVABLY outlived the session - `suppression/0220` lived 15m10s and
      launched a 51m05s suite - and no file metadata was consulted to say so.
    """
    if launcher is None:
        return FATE_UNKNOWN, (
            "no lane session could be tied to this launch, so whether "
            "anybody read its result is not a question this reader can "
            "answer")
    if launcher["done"] is None:
        return FATE_RUNNING, (
            "the session that launched it (%s) has no DONE line yet, so its "
            "fate is undecided" % launcher["brief"])

    # (1) THE ARITHMETIC ROUTE. No mtime, no artefact metadata at all.
    if (attributed_by == BY_PID and wall is not None
            and launcher["start"] is not None):
        earliest = launcher["start"] + datetime.timedelta(seconds=wall)
        if earliest > launcher["done"]:
            return FATE_DIED_UNREAD, (
                "%s announced this launch and ran from %s to %s, which is "
                "%s. The suite itself took %s, so even if it had started at "
                "the session's first instant it could not have finished "
                "before %s - and the session had closed %s earlier. Proven "
                "from the session's own window and the verdict's "
                "wall_seconds, with no file timestamp consulted"
                % (launcher["brief"],
                   launcher["start"].strftime("%H:%M:%S"),
                   launcher["done"].strftime("%H:%M:%S"),
                   _plain(launcher["done"] - launcher["start"]),
                   _plain(datetime.timedelta(seconds=wall)),
                   earliest.strftime("%H:%M:%S"),
                   _plain(earliest - launcher["done"])))

    # (2) THE RESULT EXISTED IN TIME. An upper bound is enough for this
    # direction and this direction only.
    if result_upper is not None and launcher["done"] >= result_upper:
        if recorded is None:
            return FATE_UNKNOWN, (
                "the result existed by %s and the launching session %s was "
                "open until %s, and that session's own output could not be "
                "read - so whether it recorded the result is UNKNOWN"
                % (result_upper.strftime("%H:%M:%S"), launcher["brief"],
                   launcher["done"].strftime("%H:%M:%S")))
        if recorded:
            return FATE_FINISHED_READ, (
                "the result existed by %s and the launching session %s was "
                "still open until %s"
                % (result_upper.strftime("%H:%M:%S"), launcher["brief"],
                   launcher["done"].strftime("%H:%M:%S")))
        return FATE_LANDED_UNRECORDED, (
            "the result existed by %s, %s before the launching session %s "
            "closed, so it could have been read - and nothing in that "
            "session's record names it"
            % (result_upper.strftime("%H:%M:%S"),
               _plain(launcher["done"] - result_upper), launcher["brief"]))

    # (3) AN UNCONTRADICTED CLOCK, compared directly.
    if result_exact is not None and launcher["done"] < result_exact:
        return FATE_DIED_UNREAD, (
            "the session that launched it, %s, closed at %s - %s before the "
            "result was written at %s, and no copy of that artefact "
            "contradicts its mtime. Nothing re-invokes a closed session"
            % (launcher["brief"], launcher["done"].strftime("%H:%M:%S"),
               _plain(result_exact - launcher["done"]),
               result_exact.strftime("%H:%M:%S")))

    # (4) NOTHING SETTLES IT. Fail closed: an unsettled launch is the hole in
    # this instrument and is never reported as a result somebody read.
    if result_upper is None:
        return FATE_UNKNOWN, (
            "the launching session %s closed at %s, and no result for this "
            "launch is readable here. Nothing proves one was never written "
            "either: it may sit at the fixed path inside a lane worktree, "
            "which this reader may not open"
            % (launcher["brief"], launcher["done"].strftime("%H:%M:%S")))
    return FATE_UNKNOWN, (
        "the launching session %s closed at %s and the only clock this "
        "launch carries is an mtime of %s that a byte-identical copy "
        "contradicts. An upper bound later than the session's close proves "
        "nothing in either direction, so this launch is UNKNOWN rather than "
        "charged as unread"
        % (launcher["brief"], launcher["done"].strftime("%H:%M:%S"),
           result_upper.strftime("%H:%M:%S")))


def _plain(delta):
    """A timedelta as bare words. Seconds matter here: 81 of them is the whole
    margin by which `suppression/0220` missed its own result."""
    total = int(round(delta.total_seconds()))
    if total < 60:
        return "%ds" % total
    if total < 3600:
        return "%dm%02ds" % (total // 60, total % 60)
    return "%dh%02dm" % (total // 3600, (total % 3600) // 60)


def _lock_disposition(pid, lock_pid, lock_alive, lock_readable):
    """`(state, why)` for the lock, asked about THIS launch's pid.

    Independent of the fate by construction: this function cannot see a
    session, a DONE line or a result, and `_classify` cannot see a lock.
    """
    if not lock_readable:
        return LOCKD_UNDETERMINED, (
            "the lock authority could not be consulted, so whether this run "
            "released it is UNKNOWN")
    if pid is None:
        return LOCKD_UNDETERMINED, (
            "no pid could be established for this launch, so the lock cannot "
            "be asked about it. Not released")
    if lock_pid != pid:
        return LOCKD_RELEASED, (
            "the lock file does not name pid %d, so this run released it%s"
            % (pid, "" if lock_pid is None
               else " (it now names pid %d)" % lock_pid))
    if lock_alive is None:
        return LOCKD_UNDETERMINED, (
            "the lock names pid %d and the process table could not be read, "
            "so the holder is neither alive nor dead here. A holder is never "
            "called dead on a failed read" % pid)
    if lock_alive:
        return LOCKD_LIVE, (
            "the lock names pid %d and that pid is in the process table" % pid)
    return LOCKD_STRANDED, (
        "the lock still names pid %d and that pid is NOT in the process "
        "table. `run_suite` releases in a `finally`, so this run was killed "
        "before it could write a verdict" % pid)


def launches(root=None, now=None, probe=None, table=None, lock_path=None):
    """Every suite launch this estate can evidence, each with a fate.

    Read-only: nothing is written, no lock is touched, no process is signalled
    and no lane worktree is opened.
    """
    now = now or datetime.datetime.now()
    root = root or lanes.ops_root()
    if root is None:
        return {"state": lanes.UNCONFIGURED, "rows": [], "at": now,
                "variable": lanes.OPS_DIR}
    probe = probe or lanes.SystemProbe()
    if table is None:
        table = probe.table()

    trees = _lane_trees(root)
    lock_rows, resolved_lock = lock_launches(
        file_path=lock_path, probe=probe, table=table)
    lock_readable = resolved_lock is not None
    lock_pid = lock_rows[0]["pid"] if lock_rows else None
    lock_alive = lock_rows[0]["alive"] if lock_rows else None
    if lock_readable and not lock_rows:
        # The path resolved and the file named no usable holder. That is
        # "no live claim on the lock" for the purpose of asking about a pid,
        # and it is NOT a failure to consult the authority.
        lock_pid, lock_alive = None, None

    # Per-lane reads, done once each rather than once per launch.
    session_rows, session_state, outs = {}, {}, {}
    for lane, _where in lanes.lane_names(root):
        rows, state, truncated = sessions(root, lane)
        session_rows[lane] = rows
        session_state[lane] = {"state": state, "truncated": truncated}
        outs[lane] = out_records(root, lane)

    groups, walked, capped = artefacts(root)
    rows = []

    # ------------------------------------------------- the verdict route
    for md5 in sorted(groups, key=lambda k: groups[k]["earliest"]):
        group = groups[md5]
        wall = _wall_seconds(group["fields"])
        lane = _lane_of_tree(group["fields"].get("log_file"), trees)
        result_at = group["earliest"]
        clock = TIME_CLOBBERED if group["clobbered"] else TIME_MTIME
        launch_at = (result_at - datetime.timedelta(seconds=wall)
                     if wall is not None else None)
        launcher, how, attributed_by = None, None, None
        if lane is not None:
            # THE PID ROUTE FIRST, because it survives a clobbered mtime.
            # Several sessions of a lane may name a pid; the EARLIEST is the
            # launcher, because a launch is announced by whoever made it
            # before anybody else can observe it.
            if group["pid"] is not None and outs.get(lane):
                pattern = re.compile(r"\b%d\b" % group["pid"])
                for record in outs[lane]:
                    if record["text"] and pattern.search(record["text"]):
                        launcher = _session_at(session_rows[lane],
                                               record["start"])
                        if launcher is not None:
                            attributed_by = BY_PID
                            how = ("the earliest `.out` of this lane naming "
                                   "pid %d is %s" % (group["pid"],
                                                     record["name"]))
                            break
            if launcher is None and clock != TIME_CLOBBERED:
                launcher = _session_at(session_rows[lane], launch_at)
                if launcher is not None:
                    attributed_by = BY_TIME
                    how = ("the session open at the launch time derived from "
                           "this artefact's mtime")
            if launcher is None and clock == TIME_CLOBBERED:
                how = ("no pid is in this artefact's name and its mtime is "
                       "contradicted by a copy, so no session may be "
                       "attributed by time")
        else:
            how = ("`log_file=%s` is in no lane's tree, so this launch "
                   "belongs to no lane session"
                   % (group["fields"].get("log_file") or "<absent>"))

        record = None
        if launcher is not None and outs.get(lane):
            record = _session_at_out(outs[lane], launcher)
        recorded, recorded_why = (None, "no `.out` could be matched to the "
                                        "launching session")
        if record is not None:
            recorded, recorded_why = _recorded(record["text"], group,
                                               result_at)
        fate, why = _classify(
            launcher, attributed_by,
            result_upper=result_at,
            # An mtime a copy contradicts is an upper bound only. It is
            # handed to the classifier as `result_upper` and withheld as
            # `result_exact`, which is the whole difference between proving
            # a result landed in time and inventing a late landing.
            result_exact=None if group["clobbered"] else result_at,
            wall=wall, recorded=recorded)
        lockd, lockd_why = _lock_disposition(group["pid"], lock_pid,
                                             lock_alive, lock_readable)
        rows.append({
            "source": "verdict",
            "md5": md5,
            "lane": lane,
            "pid": group["pid"],
            "status": group["fields"].get("status"),
            "failures": group["fields"].get("failures"),
            "wall_seconds": wall,
            "log_file": group["fields"].get("log_file"),
            "launch_at": launch_at,
            "launch_clock": clock,
            "result_at": result_at,
            "result_clock": clock,
            "copies": [c["rel"] for c in group["copies"]],
            "copy_count": len(group["copies"]),
            "artefact": group["copies"][0]["rel"],
            "launcher": launcher["brief"] if launcher else None,
            "launcher_start": launcher["start"] if launcher else None,
            "launcher_done": launcher["done"] if launcher else None,
            "launcher_suffix": launcher["suffix"] if launcher else None,
            "attributed_by": attributed_by,
            "attribution": how,
            "recorded": recorded,
            "recorded_why": recorded_why,
            "fate": fate,
            "why": why,
            "lock_disposition": lockd,
            "lock_why": lockd_why,
        })

    # ---------------------------------------------------- the lock route
    #
    # A launch the lock can see and no verdict can. Added only when no
    # verdict row already carries that pid, so one run is never two rows.
    claimed = {row["pid"] for row in rows if row["pid"] is not None}
    for entry in lock_rows:
        if entry["pid"] in claimed:
            continue
        lane = _lane_of_tree(entry["worktree"], trees)
        launcher = (_session_at(session_rows.get(lane), entry["launch_at"])
                    if lane is not None else None)
        how = (("the lock records worktree=%s and started_at=%s, and that is "
                "inside this session" % (entry["worktree"],
                                         entry["launch_at"]))
               if launcher is not None else
               ("the lock records worktree=%s, which is in no lane's tree"
                % entry["worktree"]))
        lockd, lockd_why = _lock_disposition(entry["pid"], lock_pid,
                                            lock_alive, lock_readable)
        # A STRANDED lock is positive proof no verdict was written, because
        # `release()` is in a `finally`. That is the one case where "no
        # result is readable" may be upgraded from UNKNOWN to "there is no
        # result", and it is upgraded HERE rather than inside `_classify`,
        # which must stay unable to see a lock.
        if lockd == LOCKD_STRANDED and launcher is not None:
            if launcher["done"] is None:
                fate, why = FATE_RUNNING, (
                    "the session that launched it, %s, has not closed yet"
                    % launcher["brief"])
            else:
                fate = FATE_DIED_UNREAD
                why = ("this run was killed before it could write a verdict - "
                       "the lock it took at %s still names dead pid %d - and "
                       "the session that launched it, %s, closed at %s. There "
                       "was never a result and there is no longer anybody to "
                       "read one"
                       % (entry["launch_at"], entry["pid"],
                          launcher["brief"],
                          launcher["done"].strftime("%H:%M:%S")))
        else:
            fate, why = _classify(launcher, BY_LOCK, None, None, None, None)
        rows.append({
            "source": "lock",
            "md5": None,
            "lane": lane,
            "pid": entry["pid"],
            "status": None,
            "failures": None,
            "wall_seconds": None,
            "log_file": None,
            "launch_at": entry["launch_at"],
            "launch_clock": entry["launch_clock"],
            "result_at": None,
            "result_clock": TIME_NONE,
            "copies": [],
            "copy_count": 0,
            "artefact": None,
            "branch": entry["branch"],
            "worktree": entry["worktree"],
            "launcher": launcher["brief"] if launcher else None,
            "launcher_start": launcher["start"] if launcher else None,
            "launcher_done": launcher["done"] if launcher else None,
            "launcher_suffix": launcher["suffix"] if launcher else None,
            "attributed_by": BY_LOCK if launcher else None,
            "attribution": how,
            "recorded": None,
            "recorded_why": ("this run wrote no result, so there was nothing "
                             "to record"),
            "fate": fate,
            "why": why,
            "lock_disposition": lockd,
            "lock_why": lockd_why,
        })

    rows.sort(key=lambda r: (r["launch_at"] or r["result_at"] or
                             datetime.datetime.min))
    return {
        "state": lanes.PRESENT,
        "root": root,
        "variable": lanes.OPS_DIR,
        "at": now,
        "rows": rows,
        "table_read": table is not None,
        "lock_readable": lock_readable,
        "lock_path": resolved_lock,
        "artefacts_walked": walked,
        "artefacts_capped": capped,
        "sessions": session_state,
        "trees": {tree: lane for tree, lane in trees.items()},
    }


def _session_at_out(records, launcher):
    """The `.out` belonging to this session, by the watcher's own stamp.

    The watcher builds the `.out` name and the DONE entry from one `$stamp`,
    so a session that started at `t` has the `.out` whose stamp is `t`. A
    five-second tolerance is allowed because the watcher stamps before it
    launches; anything wider would let a neighbouring session's final answer
    stand in for this one's.
    """
    if records is None or launcher.get("start") is None:
        return None
    best = None
    for record in records:
        if record["start"] is None:
            continue
        gap = abs((record["start"] - launcher["start"]).total_seconds())
        if gap <= lanes.OUT_JOIN_TOLERANCE_SECONDS + 3:
            if best is None or gap < best[0]:
                best = (gap, record)
    return best[1] if best else None


def panel(root=None, now=None, probe=None, table=None, lock_path=None):
    """Per-lane counts with their denominators, and the cost in minutes.

    A ZERO MUST NOT RENDER LIKE NO DATA, so every lane row carries
    `decided` - how many launches of that lane's are classifiable at all.
    A lane with `decided=0` has told this reader nothing; a lane with
    `decided=4, unread=0` has told it something good. The page can only keep
    those apart if the data does.
    """
    data = launches(root=root, now=now, probe=probe, table=table,
                    lock_path=lock_path)
    if data["state"] != lanes.PRESENT:
        return data
    rows = data["rows"]

    by_lane = {}
    for lane, _where in lanes.lane_names(data["root"]):
        by_lane[lane] = {"lane": lane, "launches": 0, "decided": 0,
                         "read": 0, "unread": 0, "unrecorded": 0,
                         "running": 0, "unknown": 0,
                         "unread_seconds": 0.0, "unread_unmeasured": 0}
    unattributed = {"lane": None, "launches": 0, "decided": 0, "read": 0,
                    "unread": 0, "unrecorded": 0, "running": 0, "unknown": 0,
                    "unread_seconds": 0.0, "unread_unmeasured": 0}
    for row in rows:
        bucket = by_lane.get(row["lane"], unattributed)
        bucket["launches"] += 1
        if row["fate"] in DECIDED:
            bucket["decided"] += 1
        if row["fate"] == FATE_FINISHED_READ:
            bucket["read"] += 1
        elif row["fate"] == FATE_DIED_UNREAD:
            bucket["unread"] += 1
            if row["wall_seconds"] is not None:
                bucket["unread_seconds"] += row["wall_seconds"]
            else:
                # A killed run's burn is between zero and now-minus-launch
                # and nothing readable here narrows it. Counted as a launch
                # whose cost is UNMEASURED rather than folded in as a zero,
                # which would make a dead suite look free.
                bucket["unread_unmeasured"] += 1
        elif row["fate"] == FATE_LANDED_UNRECORDED:
            bucket["unrecorded"] += 1
        elif row["fate"] == FATE_RUNNING:
            bucket["running"] += 1
        else:
            bucket["unknown"] += 1

    lane_rows = [by_lane[lane] for lane in sorted(by_lane)]
    if unattributed["launches"]:
        lane_rows.append(unattributed)

    tally = {}
    for row in rows:
        tally[row["fate"]] = tally.get(row["fate"], 0) + 1
    locks = {}
    for row in rows:
        locks[row["lock_disposition"]] = locks.get(
            row["lock_disposition"], 0) + 1

    unread_rows = [r for r in rows if r["fate"] == FATE_DIED_UNREAD]
    data.update({
        "lane_rows": lane_rows,
        "tally": tally,
        "lock_tally": locks,
        "total": len(rows),
        "decided": len([r for r in rows if r["fate"] in DECIDED]),
        "unread": len(unread_rows),
        "read": tally.get(FATE_FINISHED_READ, 0),
        "unknown": tally.get(FATE_UNKNOWN, 0),
        # THE COST FIGURE, and the one a person acts on.
        "unread_seconds": sum(r["wall_seconds"] for r in unread_rows
                              if r["wall_seconds"] is not None),
        "unread_unmeasured": len([r for r in unread_rows
                                  if r["wall_seconds"] is None]),
        # THE INDEPENDENCE, as a number rather than a claim: how many
        # died-unread launches released their lock cleanly. A non-zero here
        # is the proof that ORPHAN cannot stand in for DIED-UNREAD.
        "unread_lock_released": len(
            [r for r in unread_rows
             if r["lock_disposition"] == LOCKD_RELEASED]),
        "unread_lock_stranded": len(
            [r for r in unread_rows
             if r["lock_disposition"] == LOCKD_STRANDED]),
        "fate_glossary": [{"state": key, "label": label, "why": why}
                          for key, (label, why) in sorted(FATE_TEXT.items())],
        "lock_glossary": [{"state": key, "label": label, "why": why}
                          for key, (label, why)
                          in sorted(LOCKD_TEXT.items())],
        "clock_glossary": [{"state": key, "label": label, "why": why}
                           for key, (label, why) in sorted(TIME_TEXT.items())],
    })
    return data


def describe(data=None):
    """What this module answers and what it refuses to, as plain text."""
    return [
        "DIED-UNREAD is a fact about a SESSION; ORPHAN is a fact about a "
        "LOCK. They are measured separately and either can occur without "
        "the other.",
        "A launch is evidenced by the lock (pid, started_at, worktree) or by "
        "a verdict (log_file, wall_seconds, pid in its filename). A pid "
        "mentioned in a session's prose is not evidence that the session "
        "launched it.",
        "A verdict carries no timestamp, so its only clock is an mtime - and "
        "an mtime contradicted by a byte-identical copy is not used to "
        "attribute a session.",
        "This module writes nothing, clears no lock, signals no process and "
        "opens no lane worktree.",
    ]
