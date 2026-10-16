"""The floor nobody can prove was breached: a time series of queue depth.

WHY THIS EXISTS. `queue/README.md` carries the operator's floor - never leave
a lane below three queued briefs - and `0080` measured what breaking it costs
over 2026-10-15 01:30 -> 2026-10-16 00:45: **28% estate utilisation, 89.9 of
the 94.3 lane-hours lost to gaps were an EMPTY QUEUE rather than a broken
lane, and one shared gap, 03:21 -> 18:02, was 46.8 lane-hours on its own.**

`0080`'s panel answers the question for RIGHT NOW. That is not enough, and the
reason is the shape of the instrument rather than the quality of its reading:
a board showing CURRENT depth goes green the instant somebody tops a queue up,
and the hours that were lost leave no trace in any file in this estate. Two
further breaches happened while `0080` itself was running - `suppression` at
depth 0 with nothing in `RUNNING` since 02:40, `webapp` at depth 0 behind its
running brief since 02:19 - and both were found by a person reading `queue/`
at 02:46. Nobody can answer "how much autonomy did we lose to starvation
yesterday" from any file here, which is why that 89.9 had to be reconstructed
by hand.

So: one row per lane per render, appended to a ledger, never rewritten.

THE WAY THIS WOULD LIE, which is why most of what follows refuses rather than
counts. A ledger created today makes an estate that has starved all week look
as though it never has. **Everything before the first row is UNKNOWN, not
zero**, and so is everything after the last one, and so is every gap between
two rows further apart than a sample is allowed to reach. None of those is
interpolated, none is filled with the previous value, and none is counted as
healthy - a lane that stopped being sampled is not a lane that stopped
breaching the floor. Zero rows is not zero breaches.

TWO DISTINCTIONS THIS MODULE KEEPS AND WILL NOT COLLAPSE.

1. `known` is about the DURATION: could this stretch of time be attributed to
   an observed state at all. `below_floor` is about the BREACH: given that it
   could, was the lane under the floor. A stretch can be attributable and
   still undecidable - depth read, floor unreadable - and that is a third
   answer, not a pass.
2. Below-floor time that overlapped WORKING is a countdown: the lane was busy
   and would have starved on finishing. Below-floor time that overlapped IDLE
   is a stopped lane: it had already starved. The second is the expensive one
   and it is the one `0080` could not see in retrospect.

WHAT THIS MODULE DOES NOT DO. It does not write, number, move or generate a
brief, and it does not top up a queue. The dispatcher takes the lowest-numbered
file in a lane's folder, and a brief invented by a measuring instrument is the
worst possible thing to put in front of it. The only file this module writes is
its own ledger under `runtime/`.
"""
import datetime
import json
import os
import re

from src import lanes


# ------------------------------------------------------------------ the file
#
# Under `runtime/` because that is where this estate's own durable runtime
# state already lives, and NOT under `queue/` or `logs/`: both of those are
# read-only to every lane by standing boundary, and a measuring instrument
# that writes into the thing it measures is the first step towards a page
# reporting on its own output.

RUNTIME_DIR = "runtime"
LEDGER_NAME = "floor-breach-ledger.jsonl"

#: Schema version, written into every row. A reader that does not recognise a
#: row's version treats the row as DAMAGED rather than guessing at its fields,
#: so a future writer cannot make this reader silently mis-count.
SCHEMA = 1

#: The longest stretch a single sample may be held to speak for. Beyond it the
#: stretch is UNKNOWN.
#:
#: THIS IS NOT A SAMPLING INTERVAL AND MUST NOT BE READ AS ONE. The ledger
#: grows when the page is RENDERED, by a person or a check opening it, so the
#: real spacing between rows is a fact about how often somebody looked - not
#: about the estate, and not under this module's control. That is precisely
#: why a ceiling is needed: without one, a ledger looked at twice a day would
#: attribute twelve hours of estate behaviour to a single reading of it and
#: produce a confident total about a window nobody observed.
#:
#: Ten minutes, because the watcher's own idle heartbeat is five
#: (`lanes.IDLE_HEARTBEAT_SECONDS`) and two heartbeats is the shortest span
#: over which a lane's own log would have had something to say. A reader that
#: wants a different ceiling passes one; nothing here defaults silently.
MAX_SAMPLE_GAP_SECONDS = 600

#: How far back a total is asked for by default. A day, because the
#: measurement that produced the floor was over a day.
WINDOW_SECONDS = 24 * 3600

#: The cap on how much ledger is read in one render. The file is one short
#: line per lane per render; at seven lanes and a render a minute that is
#: about 70 MB a year, so a cap is needed and a SILENT one would be this
#: repository's own failure family. When it bites, `read` says so and every
#: total above it is refused rather than computed from the tail.
MAX_LEDGER_BYTES = 8 * 1024 * 1024


# -------------------------------------------------------------- ledger states
#
# The same five words `src.lanes` uses for an authority it could not read,
# plus one this file needs and that one does not: a ledger whose cap bit.

ABSENT = lanes.ABSENT
UNREADABLE = lanes.UNREADABLE
EMPTY = lanes.EMPTY
PRESENT = lanes.PRESENT

#: Readable, and more of it than `MAX_LEDGER_BYTES`. NOT `PRESENT`: a tail is
#: not the ledger, and a coverage claim computed from a tail would say the
#: estate's history begins where this reader's buffer does.
OVERSIZE = "oversize"


# ------------------------------------------------- what a sample's state means
#
# The bucket a below-floor stretch is charged to. The verdict comes from
# `src.lanes`, so this module invents no lane state of its own and a verdict
# added there cannot be silently absorbed into one of these.

WORKING = "working"      # busy now, and would have starved on finishing
IDLE_ = "idle"           # nothing running: it had already starved
OTHER = "other"          # neither, and the verdict is named rather than binned

#: WORKING is one verdict and one only. `V_STUCK`, `V_STALLED` and `V_DOWN`
#: all have an open task in the log and all three are doing no work, so
#: counting them as busy would charge a dead lane's hours to a countdown.
WORKING_VERDICTS = (lanes.V_RUNNING,)

#: IDLE is "consuming nothing and nothing is wrong with it". A lane that has
#: never run is idle in exactly the sense that matters here: a brief put in
#: front of it would be taken.
IDLE_VERDICTS = (lanes.V_IDLE, lanes.V_NEVER_RAN)

BUCKET_TEXT = {
    WORKING: ("WORKING",
              "a task was open and alive, so the lane was busy and would "
              "have starved on finishing. This is a countdown"),
    IDLE_: ("IDLE",
            "nothing was running, so the lane had ALREADY starved. These are "
            "the minutes that were actually lost"),
    OTHER: ("neither",
            "the lane was STUCK, STALLED, DOWN, ORPHANED, UNCROSSED or "
            "UNKNOWN. None of those is busy and none of them is a lane "
            "waiting for work, so the time is charged to neither bucket and "
            "the verdict is named instead"),
}


def bucket_for(verdict):
    """Which bucket a sample's lane verdict belongs to. Never a guess."""
    if verdict in WORKING_VERDICTS:
        return WORKING
    if verdict in IDLE_VERDICTS:
        return IDLE_
    return OTHER


# ----------------------------------------------------------------- the floor
#
# Read from the operator's own file. See `lanes.read_floor`: the floor is NOT
# a constant in this codebase, because a floor written in code is the
# hand-kept denominator and it fails in the one direction that matters - the
# operator raises it in his file, the instrument keeps comparing against the
# old number, and every lane reads compliant.
#
# Each ROW carries the floor that was in force when it was taken, so a floor
# that changes is visible in the series rather than applied backwards over
# history that was judged against a different number. A row with no floor is
# UNDECIDABLE, never compliant.


def ledger_path(root=None):
    """Absolute path of the ledger, or None when nothing says where it is."""
    root = root or lanes.ops_root()
    if root is None:
        return None
    return os.path.join(root, RUNTIME_DIR, LEDGER_NAME)


# ------------------------------------------------------------------- writing


def sample_rows(board, at=None):
    """One row per lane, from a `lanes.board()` reading. Writes nothing.

    `at` is THE RENDER's time and every row of one render carries the same
    one. That is deliberate and the span arithmetic depends on it: a hole in
    the file has to be locatable in every lane's series at once, and per-lane
    read times drifting by a few hundred milliseconds would make the same
    moment fall on different sides of a boundary in different lanes.

    Four facts per lane and no derived ones. `depth` and `running` and
    `state` and `floor` are what was observed; every total is computed from
    them later, so a change to how a breach is counted does not need the
    history to be rewritten - which is just as well, because it may not be.
    """
    if board.get("state") != PRESENT:
        return []
    at = at or board.get("at") or datetime.datetime.now()
    stamp = at.strftime(lanes._STAMP)
    rows = []
    for row in board.get("lanes", []):
        rows.append({
            "v": SCHEMA,
            "at": stamp,
            "lane": row["lane"],
            # None when the queue folder could not be read. NOT 0: an
            # unreadable queue is neither a breach of the floor nor
            # compliance with it, and a 0 here would be the loudest possible
            # version of the lie this whole module exists to prevent.
            "depth": row["queue_depth"],
            # Recorded because the brief asks for it, and FOR RECONCILIATION
            # ONLY. `0080` measured this signal wrong in both directions: an
            # empty `RUNNING/` is not an idle lane and a full one is not a
            # busy lane - two lanes sat with a brief in `RUNNING/` whose
            # owner was dead, for 97 minutes each. The WORKING/IDLE split
            # below is taken from the verdict, never from this.
            "running": (None if row["running_state"] != PRESENT
                        else bool(row["inflight"])),
            # The crossed verdict from `src.lanes`, not the log's own status:
            # the log says RUNNING for a stuck lane and that is the error
            # this estate paid 7.66 lane-hours for.
            "state": row["verdict"],
            # The floor IN FORCE AT THIS SAMPLE, from `queue/README.md`.
            "floor": row["floor"],
        })
    return rows


#: What `append` did. Four answers and no bare boolean, because "wrote
#: nothing because there was nothing to write" and "wrote nothing because the
#: disk refused" must not render as the same thing on a page whose whole
#: subject is a missing row.
WRITTEN = "written"
NOTHING_TO_WRITE = "nothing_to_write"
UNWRITABLE = "unwritable"
UNCONFIGURED_WRITE = "unconfigured"

#: A fifth, and it is about this RENDER rather than about the estate: nobody
#: asked for a sample. Kept apart from `NOTHING_TO_WRITE` because that one
#: says the board read no lane, which is a claim about the estate - and a
#: read-only render reporting it was making a false one.
NOT_SAMPLED = "not_sampled"

APPEND_TEXT = {
    WRITTEN: "appended",
    NOTHING_TO_WRITE: "nothing to append - the board read no lane at all, so "
                      "this render contributed no sample and the coverage "
                      "below does not grow",
    NOT_SAMPLED: "this render was read-only and took no sample, so the "
                 "ledger did not grow and the stretch since its last row "
                 "stays UNKNOWN",
    UNWRITABLE: "THE LEDGER COULD NOT BE WRITTEN. This render is not in the "
                "history, and the gap it leaves reads as UNKNOWN rather than "
                "as healthy",
    UNCONFIGURED_WRITE: "no ledger path: nothing says where the lane estate "
                        "is",
}


def append(path, rows):
    """Append rows to the ledger. APPEND ONLY; no row is ever rewritten.

    Opened `"a"` and never `"w"`, `"r+"` or a read-modify-write: the file is
    the only record of what was observed, and a reader that can rewrite it
    can quietly repair its own history. A write that fails is REPORTED rather
    than swallowed - a ledger silently not growing is indistinguishable from
    an estate that never breached, and that is the failure this module is.
    """
    if path is None:
        return {"state": UNCONFIGURED_WRITE, "written": 0, "path": None,
                "error": "nothing says where the lane estate is"}
    if not rows:
        return {"state": NOTHING_TO_WRITE, "written": 0, "path": path,
                "error": None}
    try:
        parent = os.path.dirname(path)
        if parent and not os.path.isdir(parent):
            os.makedirs(parent, exist_ok=True)
        # One `write` of one joined blob rather than a `write` per row, so a
        # render's rows land together: a crash between two of them would
        # leave a render half-recorded, and the gap detector would read that
        # as a lane that stopped being sampled while its neighbours carried
        # on.
        blob = "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows)
        with open(path, "a", encoding="utf-8", newline="\n") as handle:
            handle.write(blob)
            handle.flush()
    except (OSError, TypeError, ValueError) as error:
        return {"state": UNWRITABLE, "written": 0, "path": path,
                "error": type(error).__name__}
    return {"state": WRITTEN, "written": len(rows), "path": path,
            "error": None}


# ------------------------------------------------------------------- reading


def read(path, max_bytes=MAX_LEDGER_BYTES):
    """Parse the ledger. `{state, rows, damaged, ...}`.

    FOUR OUTCOMES THAT ARE NOT ROWS, kept apart because they are different
    facts and a page that renders them identically has learnt nothing: no
    file at all, a file that could not be opened, a file with no bytes, and a
    file larger than this reader will hold.

    A row that does not parse is NOT SKIPPED. It becomes a `damaged` marker at
    its file position, and `spans` below turns every stretch that straddles
    that position into UNKNOWN - for every lane, because a line whose JSON is
    broken may not even say which lane it was about. Its position in the file
    is still a real bound on WHEN it happened, since the file is appended in
    time order, and that bound is what makes the window it poisons finite
    rather than the whole ledger.
    """
    if path is None:
        return {"state": ABSENT, "path": None, "rows": [], "damaged": [],
                "lines": 0, "oversize": False}
    if not os.path.exists(path):
        return {"state": ABSENT, "path": path, "rows": [], "damaged": [],
                "lines": 0, "oversize": False}
    try:
        size = os.path.getsize(path)
        if size > max_bytes:
            # NOT truncated to a tail. A tail would make the first row of the
            # buffer look like the first row of the history, and the coverage
            # line - the most load-bearing sentence on the page - would then
            # be a statement about this reader's buffer size.
            return {"state": OVERSIZE, "path": path, "rows": [],
                    "damaged": [], "lines": 0, "oversize": True,
                    "bytes": size, "max_bytes": max_bytes}
        with open(path, "rb") as handle:
            blob = handle.read()
    except OSError:
        return {"state": UNREADABLE, "path": path, "rows": [], "damaged": [],
                "lines": 0, "oversize": False}
    text = blob.decode("utf-8", "replace")
    if text.startswith("﻿"):
        text = text[1:]
    raw = [line for line in text.splitlines() if line.strip()]
    if not raw:
        return {"state": EMPTY, "path": path, "rows": [], "damaged": [],
                "lines": 0, "oversize": False}

    rows = []
    damaged = []
    for index, line in enumerate(raw):
        parsed = _parse_row(line)
        if parsed is None:
            damaged.append({"index": index, "line_number": index + 1,
                            # Whatever could be salvaged about WHEN, so the
                            # page can say where the hole is. None is normal
                            # and the file position still bounds it.
                            "at": _salvage_stamp(line)})
            continue
        parsed["index"] = index
        parsed["line_number"] = index + 1
        rows.append(parsed)
    return {"state": PRESENT, "path": path, "rows": rows, "damaged": damaged,
            "lines": len(raw), "oversize": False}


_STAMP_ANYWHERE = re.compile(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})")


def _salvage_stamp(line):
    """A timestamp out of a line whose JSON is broken, or None.

    Best effort, and the result is never used as an authority - only to tell
    the reader roughly where the hole is. The bound that the arithmetic uses
    is the line's POSITION, which is exact.
    """
    found = _STAMP_ANYWHERE.search(line)
    if not found:
        return None
    return found.group(1)


def _parse_row(line):
    """One ledger row, or None when it is damaged.

    STRICT ON PURPOSE. `depth`, `running` and `floor` are allowed to be null -
    that is this estate's own UNKNOWN and the point of recording it - but a
    row whose `at` will not parse, whose `lane` is not a name, or whose
    version this reader does not know is damaged rather than guessed at. A
    lenient parser here would turn a writer's bug into a confident total.
    """
    try:
        data = json.loads(line)
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    if data.get("v") != SCHEMA:
        return None
    when = lanes._parse_stamp(data.get("at"))
    if when is None:
        return None
    lane = data.get("lane")
    if not isinstance(lane, str) or not lane.strip():
        return None
    depth = data.get("depth")
    if depth is not None and (isinstance(depth, bool)
                              or not isinstance(depth, int) or depth < 0):
        return None
    floor = data.get("floor")
    if floor is not None and (isinstance(floor, bool)
                              or not isinstance(floor, int) or floor < 0):
        return None
    running = data.get("running")
    if running is not None and not isinstance(running, bool):
        return None
    state = data.get("state")
    if state is not None and not isinstance(state, str):
        return None
    return {"at": data["at"], "when": when, "lane": lane, "depth": depth,
            "floor": floor, "running": running, "state": state}


# --------------------------------------------------------------- the spans
#
# A sample is an instant. A breach is a duration. Turning the first into the
# second is the whole of the arithmetic, and the only honest way to do it is
# to let each sample speak for the stretch up to the NEXT sample and for no
# longer - which means the newest sample speaks for nothing at all, and the
# page says so. One reading is not a duration.


def spans(parsed, lane, max_gap_seconds=MAX_SAMPLE_GAP_SECONDS):
    """Every stretch between two consecutive samples of one lane.

    Each stretch is attributed to the state observed at its START, held until
    the next observation and NO FURTHER. That is the only direction that can
    be defended: the earlier sample is something that was seen, and holding
    it forward past the gap ceiling would be exactly the carry-forward this
    module refuses.

    Four ways a stretch comes out `known=False`, and not one of them is
    counted as healthy:

      gap        the two samples are further apart than `max_gap_seconds`
      damaged    a row that would not parse sits between them in the file
      disorder   the later sample is stamped before the earlier one
      ...

    and the fourth is not here but in `window`: the stretches before the
    first row and after the last one.
    """
    series = [row for row in parsed["rows"] if row["lane"] == lane]
    damaged = parsed["damaged"]
    out = []
    for earlier, later in zip(series, series[1:]):
        seconds = (later["when"] - earlier["when"]).total_seconds()
        # A damaged line BETWEEN these two positions in the file. Positional,
        # not timestamped: the broken line may carry no readable time, and
        # the file's append order is a real bound either way.
        holed = [d for d in damaged
                 if earlier["index"] < d["index"] < later["index"]]
        if seconds < 0:
            out.append(_unknown_span(earlier, later, "disorder"))
            continue
        if holed:
            out.append(_unknown_span(earlier, later, "damaged"))
            continue
        if seconds > max_gap_seconds:
            out.append(_unknown_span(earlier, later, "gap"))
            continue
        out.append(_known_span(earlier, later, int(seconds)))
    return out


def _unknown_span(earlier, later, why):
    """An unattributable stretch, bounded by the two readings either side.

    THE ENDS ARE ORDERED BY TIME AND NOT BY FILE POSITION. For a gap or a
    damaged row they are the same thing, but for `disorder` they are not -
    the later row is stamped BEFORE the earlier one, and taking the ends in
    file order produced a span running backwards. A backwards span clips to
    nothing against any window, so the hole silently vanished and the two
    readings read as covered. Measured while writing the control for it.
    """
    low = min(earlier["when"], later["when"])
    high = max(earlier["when"], later["when"])
    return {"lane": earlier["lane"], "from": low, "to": high,
            "known": False, "why": why,
            "seconds": int((high - low).total_seconds()),
            "depth": None, "floor": None, "state": None, "running": None,
            "at_zero": None, "below_floor": None, "bucket": None}


def _known_span(earlier, later, seconds):
    depth = earlier["depth"]
    floor = earlier["floor"]
    # Three answers, and the third is the one that gets lost. Depth read and
    # floor unreadable is UNDECIDABLE: it is not a breach, and it is very
    # much not compliance.
    if depth is None or floor is None:
        below = None
    else:
        below = depth < floor
    return {"lane": earlier["lane"], "from": earlier["when"],
            "to": later["when"], "known": True, "why": None,
            "seconds": seconds, "depth": depth, "floor": floor,
            "state": earlier["state"], "running": earlier["running"],
            "at_zero": None if depth is None else depth == 0,
            "below_floor": below, "bucket": bucket_for(earlier["state"])}


def _clip(span, start, end):
    """The part of a span inside `[start, end]`, or None. Never negative."""
    low = max(span["from"], start)
    high = min(span["to"], end)
    if high <= low:
        return None
    out = dict(span)
    out["from"] = low
    out["to"] = high
    out["seconds"] = int((high - low).total_seconds())
    return out


# ------------------------------------------------------------- the coverage
#
# PRINTED ABOVE EVERY TOTAL, in the same visual weight. This is the single
# most likely way for the page to lie, and it is not a subtle lie: a ledger
# created five minutes ago reports zero below-floor minutes for the last day,
# which reads as an estate that has never starved.


def coverage(parsed, lane, now, window_seconds=WINDOW_SECONDS,
             max_gap_seconds=MAX_SAMPLE_GAP_SECONDS):
    """What this ledger can and cannot speak for, for one lane.

    `first` and `last` are the lane's own first and last row - not the
    file's: a lane added yesterday has a shorter history than the ledger, and
    reporting the file's span as its coverage would credit it with hours
    nobody sampled it for.
    """
    series = [row for row in parsed["rows"] if row["lane"] == lane]
    start = now - datetime.timedelta(seconds=window_seconds)
    if not series:
        return {"lane": lane, "rows": 0, "first": None, "last": None,
                "window_from": start, "window_to": now,
                "holes": [{"from": start, "to": now,
                           "seconds": int((now - start).total_seconds()),
                           "why": "no_rows"}],
                "covered_seconds": 0,
                "unknown_seconds": int((now - start).total_seconds()),
                "covers_window": False}
    # BY TIME, NOT BY FILE POSITION, for the same reason `_unknown_span`
    # orders its ends that way: a ledger with an out-of-order row would
    # otherwise report a first row later than its last, and the two holes
    # computed from them would both come out empty.
    first = min(row["when"] for row in series)
    last = max(row["when"] for row in series)
    holes = []
    # BEFORE THE FIRST ROW. The sentence this whole task is about: that
    # stretch is UNKNOWN and it is not zero. It is a hole whether the ledger
    # is five minutes old or five days old, and it shrinks only by the ledger
    # getting older.
    if first > start:
        holes.append({"from": start, "to": first,
                      "seconds": int((first - start).total_seconds()),
                      "why": "before_first_row"})
    for span in spans(parsed, lane, max_gap_seconds):
        if span["known"]:
            continue
        clipped = _clip(span, start, now)
        if clipped:
            holes.append({"from": clipped["from"], "to": clipped["to"],
                          "seconds": clipped["seconds"],
                          "why": clipped["why"]})
    # AFTER THE LAST ROW. One sample is not a duration: nothing observed the
    # lane between the newest row and now, so that stretch is UNKNOWN too -
    # including the sample this very render just wrote.
    if last < now:
        holes.append({"from": last, "to": now,
                      "seconds": int((now - last).total_seconds()),
                      "why": "after_last_row"})
    unknown = sum(hole["seconds"] for hole in holes)
    whole = int((now - start).total_seconds())
    return {"lane": lane, "rows": len(series), "first": first, "last": last,
            "window_from": start, "window_to": now, "holes": holes,
            "covered_seconds": max(0, whole - unknown),
            "unknown_seconds": unknown,
            "covers_window": not holes}


HOLE_TEXT = {
    "no_rows": "this lane has no row in the ledger at all, so nothing is "
               "known about it over this window - which is not the same as "
               "nothing having happened",
    "before_first_row": "before the ledger's first row for this lane. "
                        "UNKNOWN, not zero: the ledger starts when it was "
                        "created, and the estate did not",
    "after_last_row": "after the ledger's last row. One sample is not a "
                      "duration - nothing has observed this lane since, "
                      "including this render",
    "gap": "two samples further apart than a single reading may speak for. "
           "NOT interpolated and NOT carried forward: a lane that stopped "
           "being sampled is not a lane that stopped breaching the floor",
    "damaged": "a ledger row between these two samples could not be parsed, "
               "so this stretch is UNKNOWN rather than skipped",
    "disorder": "the later sample is stamped before the earlier one, so "
                "neither can be held to speak for the stretch between them",
    "undecidable": "the stretch was observed, and whether it was a breach "
                   "could not be decided: the queue depth or the floor was "
                   "UNKNOWN at the sample that speaks for it",
}


# ---------------------------------------------------------------- the totals


def lane_window(parsed, lane, now, window_seconds=WINDOW_SECONDS,
                max_gap_seconds=MAX_SAMPLE_GAP_SECONDS):
    """One lane's starvation accounting over a window.

    EVERY TOTAL HERE IS ABOUT THE COVERED PART OF THE WINDOW AND SAYS SO.
    `covers_window` is the only thing that licenses reading them as a
    statement about the window itself, and it is False whenever anything at
    all is unknown - a hole, a damaged row, or a stretch whose breach could
    not be decided. A page that prints `below_floor_seconds` without
    `covers_window` beside it is the instrument this task exists to replace.
    """
    cover = coverage(parsed, lane, now, window_seconds, max_gap_seconds)
    start = cover["window_from"]
    clipped = []
    for span in spans(parsed, lane, max_gap_seconds):
        part = _clip(span, start, now)
        if part:
            clipped.append(part)

    zero = below = clean = undecidable = 0
    by_bucket = {WORKING: 0, IDLE_: 0, OTHER: 0}
    other_states = {}
    for span in clipped:
        if not span["known"]:
            continue
        if span["below_floor"] is None:
            undecidable += span["seconds"]
            continue
        if span["below_floor"]:
            below += span["seconds"]
            by_bucket[span["bucket"]] += span["seconds"]
            if span["bucket"] == OTHER:
                other_states[span["state"]] = (
                    other_states.get(span["state"], 0) + span["seconds"])
        else:
            clean += span["seconds"]
        if span["at_zero"]:
            zero += span["seconds"]

    runs = _below_runs(clipped)
    longest = max(runs, key=lambda r: r["seconds"]) if runs else None
    return {
        "lane": lane,
        "coverage": cover,
        # True only when NOTHING is unknown across the whole window. Holes
        # and undecidable stretches both disqualify it, because both are
        # ways the window was not covered.
        "covers_window": bool(cover["covers_window"] and not undecidable),
        "window_seconds": int((now - start).total_seconds()),
        # Observed and attributed, which is the denominator every ratio on
        # the page must use. NOT the window: the difference between the two
        # is `unknown_seconds`, and dividing by the window would quietly
        # charge the unobserved part to "fine".
        "observed_seconds": below + clean + undecidable,
        "depth_zero_seconds": zero,
        "below_floor_seconds": below,
        "within_floor_seconds": clean,
        # Observed, and the breach question unanswerable. Reported as its own
        # number and never folded into either of the two above.
        "undecidable_seconds": undecidable,
        "unknown_seconds": cover["unknown_seconds"],
        "below_floor_by_bucket": by_bucket,
        # Which verdicts the `other` bucket is made of, so "neither busy nor
        # waiting" is never an unexplained total.
        "other_states": sorted(other_states.items()),
        "below_floor_runs": runs,
        "longest_below_floor_run": longest,
        "floors_seen": sorted({span["floor"] for span in clipped
                               if span["known"]
                               and span["floor"] is not None}),
    }


def _below_runs(clipped):
    """Contiguous stretches below the floor, longest-first elsewhere.

    A RUN IS BROKEN BY ANYTHING THAT IS NOT A PROVEN BREACH: a stretch at or
    above the floor, an UNKNOWN stretch, or one whose breach could not be
    decided. That is the difference between "the lane was under the floor for
    four hours" and "the lane was under the floor, then nobody looked for
    three hours, then it was under the floor again" - and reporting the
    second as the first is carry-forward wearing a different hat.

    ONE GUARD ANSWERS THAT, and it did not start out that way. This function
    also carried a contiguity check - start a new run when the next breach
    span does not abut the current one - and the two made each other
    invisible: removing the reset below reddened NOTHING, through a planted
    gap and through a contiguous compliant stretch alike, because the
    contiguity check answered both. A guard that cannot be observed to fail
    is not a tested guard, and this repository has the same finding three
    times over in webapp/0100's M9.
    `clipped` carries every span including the rejected ones, so the reset
    sees every break there is and the contiguity check added nothing but a
    second answer to one question. It is gone; the reset is the guard.
    """
    runs = []
    current = None
    for span in clipped:
        breach = span["known"] and span["below_floor"] is True
        if not breach:
            current = None
            continue
        if current is None:
            current = {"from": span["from"], "to": span["to"],
                       "seconds": span["seconds"],
                       "lane": span["lane"],
                       "buckets": {span["bucket"]: span["seconds"]}}
            runs.append(current)
            continue
        current["to"] = span["to"]
        current["seconds"] += span["seconds"]
        current["buckets"][span["bucket"]] = (
            current["buckets"].get(span["bucket"], 0) + span["seconds"])
    return runs


def estate_window(parsed, lane_list, now, window_seconds=WINDOW_SECONDS,
                  max_gap_seconds=MAX_SAMPLE_GAP_SECONDS):
    """The estate total: a sum of LANE-seconds, and the lanes it rests on.

    `covers_window` is a conjunction over every lane. One lane with a hole
    makes the estate total a statement about the covered part and nothing
    more, and the page may not present it as a statement about the day.

    The unit is LANE-seconds, the same unit the 89.9 figure was in. Summing
    seven lanes' below-floor seconds produces a number larger than the
    window, which is correct and is labelled.
    """
    rows = [lane_window(parsed, lane, now, window_seconds, max_gap_seconds)
            for lane in lane_list]
    keys = ("depth_zero_seconds", "below_floor_seconds",
            "within_floor_seconds", "undecidable_seconds", "unknown_seconds")
    totals = {key: sum(row[key] for row in rows) for key in keys}
    buckets = {bucket: sum(row["below_floor_by_bucket"][bucket]
                           for row in rows)
               for bucket in (WORKING, IDLE_, OTHER)}
    runs = [run for row in rows for run in row["below_floor_runs"]]
    longest = max(runs, key=lambda r: r["seconds"]) if runs else None
    return {
        "lanes": rows,
        "lane_count": len(rows),
        "covers_window": bool(rows) and all(row["covers_window"]
                                            for row in rows),
        "lanes_not_covering": [row["lane"] for row in rows
                               if not row["covers_window"]],
        "window_seconds": int(window_seconds),
        "totals": totals,
        "below_floor_by_bucket": buckets,
        # The single worst stretch anywhere in the estate, with its lane. Not
        # a sum: the 46.8-lane-hour gap on 2026-10-15 was one window shared
        # by six lanes, and a reader needs the shape as well as the area.
        "longest_below_floor_run": longest,
        "floors_seen": sorted({floor for row in rows
                               for floor in row["floors_seen"]}),
    }


def totals_licensed(parsed):
    """Whether ANY total may be computed from this ledger at all.

    THE ONE CONDITION, NAMED AND IN ONE PLACE, so there is exactly one thing
    to mutate in order to prove the refusal can fail - and so the page cannot
    quietly acquire a second opinion about it.

    Zero rows is not zero breaches. A ledger that is absent, empty,
    unreadable or larger than this reader will hold supports NO number: not a
    total, not a zero, not a dash in a table of otherwise real figures. An
    instrument with no data printing a clean estate is a thing this codebase
    has shipped, and a table of dashes is the same lie with better manners.
    """
    return bool(parsed["state"] == PRESENT and parsed["rows"])


# ---------------------------------------------------------------- one render
#
# Sample, append, read back, account. In that order, and the read-back is not
# optional: a tool reporting success is not evidence the write landed, and
# this module's entire output is a claim about what is in a file.


def render(root=None, now=None, probe=None, samples=None,
           window_seconds=WINDOW_SECONDS,
           max_gap_seconds=MAX_SAMPLE_GAP_SECONDS, write=True):
    """The whole instrument: one sample per lane appended, then the totals.

    `write=False` for a reader that must not grow the history - a test, or a
    second render inside one request. The default is True because the page
    IS the sampler: this ledger grows when somebody looks at it, which is a
    fact about the instrument that the page states rather than hides.
    """
    now = now or datetime.datetime.now()
    board = lanes.board(root=root, now=now, probe=probe, samples=samples)
    path = ledger_path(board.get("root") or root)
    rows = sample_rows(board, at=now)
    wrote = ({"state": NOT_SAMPLED, "written": 0, "path": path,
              "error": None} if not write else append(path, rows))
    # READ BACK. Every number below comes from the file as it now stands, not
    # from the rows that were just handed to `append` - so a write that was
    # refused shows up as a hole in the coverage instead of as a number that
    # happens to agree with a sample nobody stored.
    parsed = read(path)
    lane_list = sorted({row["lane"] for row in parsed["rows"]}
                       | {row["lane"] for row in board.get("lanes", [])})
    # NOT BUILT AT ALL when the ledger licenses no total. The numbers do not
    # exist in the data, so there is nothing downstream for a renderer to
    # find and print by accident - the refusal is in the reader rather than
    # in the template.
    licensed = totals_licensed(parsed)
    estate = (estate_window(parsed, lane_list, now, window_seconds,
                            max_gap_seconds)
              if licensed and lane_list else None)
    return {
        "at": now,
        "board": board,
        "ledger": parsed,
        "append": wrote,
        "estate": estate,
        # The gate's own answer, published so the shaper above does not have
        # to re-derive it and the two cannot disagree.
        "licensed": licensed,
        "window_seconds": window_seconds,
        "max_gap_seconds": max_gap_seconds,
        # The floor, and WHERE it came from. None is UNKNOWN and the path is
        # named, because the alternative - assuming 3 - is the hand-kept
        # denominator this estate has a failure family for.
        "floor": board.get("floor"),
        "floor_state": board.get("floor_state"),
        "floor_path": board.get("floor_path"),
        "floor_line": board.get("floor_line"),
    }
