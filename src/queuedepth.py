"""Queue depth twice: the files that are there, and the ones that can run.

WHY THIS EXISTS, MEASURED 2026-10-16 05:46 AND AGAIN AT 07:50. The operator's
floor - "never leave a lane below 3 queued briefs", from `queue/README.md` -
is enforced against a count of files in `queue/<lane>/`. That count is wrong
in two directions at once, and both were live on the estate:

    glm, glm-b, glm-c   watcher down since 01:46-01:48, 3+3+4 briefs queued.
                        `below_floor` False for all three: at or above the
                        floor by file count, and not one of those briefs can
                        start.
    qwen                watcher gone since 00:58:53, 6 briefs queued and
                        `0170` still sitting in RUNNING\\. `below_floor`
                        False - the deepest queue on the estate, consuming
                        nothing.
    pilotcaps           depth 3, of which `0234` and `0235` already had
                        entries in `LANE-pilotcaps.md` at lines 10937 and
                        8673. At the floor, with one real brief left.

So sixteen briefs read as healthy depth and the hourly top-up declined three
times for exactly that reason, written down each time: *depth behind a dead
watcher cannot be consumed and hides the real number*. The board said it in
prose and the number went on saying 3.

WHAT THIS CHANGES AND WHAT IT DOES NOT. The floor is the operator's and the
sentence in `queue/README.md` is its only authority; nothing here reads a
different number or writes that file. What changes is the INPUT the floor is
compared against, and the raw count stays on the page beside it, because
those sixteen briefs are real work and a panel that hid them would be the
opposite of this one's purpose.

THE THREE SUBTRACTIONS, EACH WITH ITS OWN AUTHORITY AND NONE OF THEM GUESSED.

1. NO LIVE WATCHER -> consumable 0. The authority is the pid table, read by
   `src.lanes.board` once per render, and this module reads the row's own
   fields rather than taking a second look - two readings of one process
   table is how two numbers on one page disagree. It is a WIDER reading than
   the board's `down` verdict, deliberately: `V_DOWN` needs the log to have
   gone quiet as well, so `qwen`, whose log holds an open START, is `STALLED`
   there - and STALLED's own published text is "this lane consumes no further
   work until a person moves it". Both of those are DEAD for this question.
   Three states and the third is not a soft no: a pid file that is absent is
   AMBIGUOUS by `_read_pid_file`'s own documentation - the watcher removes it
   on a clean exit and a hard kill leaves it behind - so an absent pid file
   with no `watcher down.` line is UNKNOWN, never dead and never alive.

2. ALREADY LANDED -> not consumable work, it is a re-measurement. The
   classifier is `src.lanerework`'s, built by TASK-0160 with its own
   controls, and it is CONSUMED here rather than rebuilt: `brief_id` for the
   id a filename carries, `headings` for the lane file's entries, and
   `entries_for` for equality after normalisation. This module owns no
   heading regex, no id normaliser and no date ladder. 0160's rule that a
   lane file which is ABSENT or UNREADABLE is UNKNOWN rather than "no entry
   found" is kept exactly: an absent authority cannot clear a brief.

3. LOCKED IN `RUNNING\\` BEHIND A DEAD WATCHER. It is neither queued nor
   running and it has its own name here, because it needs a person: the
   brief has to be moved by hand before the lane takes anything else. It is
   counted in neither depth - `queue/<lane>/RUNNING` is a subdirectory and
   was never in the file count - and nothing here clears, moves or renames
   it.

FAIL-CLOSED, AND THE ORDER MATTERS. Where any subtraction cannot be
established the lane's consumable depth is UNKNOWN and its re-derived
`below_floor` is UNKNOWN with it - not the raw verdict, and not "assume
consumable". The ONE case that short-circuits is a DEAD watcher, and it is
not an exception to the rule but an upper bound: a lane whose watcher is gone
consumes nothing whatever its lane file says, so 0 is proven and the other
two subtractions could only lower it. An UNKNOWN there would throw away the
strongest alarm on the page. Every other unknown propagates.

STARVATION AND STRANDING ARE DIFFERENT EMERGENCIES WITH DIFFERENT OWNERS.
Consumable 0 with a LIVE watcher means the lane will take a brief and has
none: somebody has to write one. Consumable 0 with a DEAD watcher means the
work exists and the watcher does not: somebody has to restart it. Conflating
them is family 6 - an instrument meeting a result it has no name for and
picking the nearest name it has - and this estate has recorded it enough
times to give the two states separate words.

READ-ONLY BY CONSTRUCTION. Nothing here opens a file for writing, creates a
directory, removes anything, or runs any command at all. It calls no ledger,
no provider and no socket. `scripts/depth_panel.py` proves it on the live
estate with a write trap that raises rather than tallies.
"""
import os

from src import lanerework
from src import lanes


# ------------------------------------------------------- the watcher reading
#
# THREE STATES AND THE THIRD IS NOT A SOFT NO. A lane whose liveness cannot
# be established is UNKNOWN, which produces an UNKNOWN consumable depth -
# never a 0 (which would raise a false stranding alarm) and never a pass
# (which is the defect this whole panel exists for).

#: The pid table holds this lane's watcher and its log has not said otherwise.
W_LIVE = "live"

#: Measured gone: the log's own `watcher down.` record, or a pid file naming
#: a process the table does not hold.
W_DEAD = "dead"

#: Neither could be established. The process table could not be read, or no
#: file names this lane's watcher at all.
W_UNKNOWN = "unknown"

WATCHER_TEXT = {
    W_LIVE: ("WATCHER LIVE",
             "the pid file names a process the table holds, and this lane's "
             "log has recorded no `watcher down.`. Briefs put in front of "
             "this lane will be dispatched"),
    W_DEAD: ("WATCHER DEAD",
             "this lane dispatches nothing until a person restarts it, so "
             "its consumable depth is 0 whatever its queue folder holds"),
    W_UNKNOWN: ("WATCHER UNKNOWN",
                "liveness could not be established, so consumable depth is "
                "UNKNOWN. This is not 'probably fine' and it is not an "
                "alarm: it is an unanswered question with a named cause"),
}


# ------------------------------------------------------ why an answer is not
#
# NAMED, NEVER COUNTED. Four reasons a lane's consumable depth is UNKNOWN,
# and each one has a different repair - a restart, a `LANE-` file somebody
# has to write, a queue folder somebody has to fix, a brief somebody has to
# rename. One empty cell for all four tells a reader nothing, which is the
# finding `0160`'s panel was built around.

U_QUEUE = "queue_unreadable"
U_WATCHER = "watcher_unknown"
U_LANE_FILE = "lane_file_unreadable"
U_BRIEF_ID = "brief_carries_no_id"

UNKNOWN_TEXT = {
    U_QUEUE: ("the queue folder could not be listed, so even the RAW depth "
              "is UNKNOWN. An unreadable queue is not an empty one"),
    U_WATCHER: ("this lane's watcher liveness could not be established, so "
                "whether anything here can be consumed is unanswered"),
    U_LANE_FILE: ("`LANE-<lane>.md` is absent or could not be read, so "
                  "whether a queued brief's work has already landed cannot "
                  "be asked. An absent authority does not clear a brief - "
                  "that is `src.lanerework`'s own rule and it is kept here"),
    U_BRIEF_ID: ("a queued brief's filename carries no TASK id, so the "
                 "already-landed question cannot be put for it at all"),
}


# ------------------------------------------------------------- the lane state
#
# FIVE, and the two that matter most are the two this estate kept merging.

#: Consumable depth at or above the floor. Says nothing about the work's
#: quality and nothing about the briefs that are already landed.
S_OK = "ok"

#: Consumable 0 with a LIVE watcher. The lane will take a brief and has
#: none. The owner is whoever writes briefs.
S_STARVED = "starved"

#: A DEAD watcher with briefs queued. The work exists and cannot start. The
#: owner is whoever restarts the watcher, and the raw depth is the measure of
#: what is waiting.
S_STRANDED = "stranded"

#: A DEAD watcher with nothing queued. Not starvation - nothing is being
#: denied to a lane that could not take it - and worth its own word, because
#: a restart alone would leave it starved.
S_DEAD_EMPTY = "dead_and_empty"

#: Below the floor on consumable depth with a live watcher and some work
#: left. The ordinary alarm the floor exists to raise.
S_BELOW = "below_floor"

#: Not established. Never any of the four above.
S_UNKNOWN = "unknown"

STATE_TEXT = {
    S_OK: ("OK", "consumable depth is at or above the operator's floor"),
    S_STARVED: ("STARVED",
                "the watcher is live and there is nothing left for it to "
                "consume. It will idle on its next poll. SOMEBODY HAS TO "
                "WRITE A BRIEF"),
    S_STRANDED: ("STRANDED",
                 "the watcher is gone and briefs are queued behind it. "
                 "Nothing here will start, however deep the folder is. "
                 "SOMEBODY HAS TO RESTART THE WATCHER - and this is NOT "
                 "starvation: writing another brief would change nothing"),
    S_DEAD_EMPTY: ("DEAD AND EMPTY",
                   "the watcher is gone and nothing is queued. A restart "
                   "alone leaves this lane starved"),
    S_BELOW: ("BELOW THE FLOOR",
              "the watcher is live and consumable depth is under the "
              "operator's floor. The ordinary breach"),
    S_UNKNOWN: ("UNKNOWN",
                "consumable depth could not be established, so no verdict "
                "is available. UNKNOWN is not compliance and it is not a "
                "breach"),
}


def watcher_reading(row):
    """`(state, why)` for one board row. The pid table, read once, upstream.

    TWO WAYS TO BE DEAD AND THEY ARE CHECKED IN THIS ORDER. The log's own
    `watcher down.` record is a watcher reporting its own exit, and it
    answers even where no pid file survives - which is the state `glm`,
    `glm-b` and `glm-c` were in at 07:50, all three with no pid file at all.
    The pid table answers the other way: a file naming a process the table
    does not hold is a watcher that was taken without getting to log it.

    WHY NOT `verdict == V_DOWN`. Because `V_DOWN` requires the log to have
    gone quiet as well, and a lane holding an open START is `V_STALLED`
    instead - `qwen`, six briefs deep, watcher absent from the table. The
    board is the instrument and these are its fields; the threshold for THIS
    question is simply wider than the one for that verdict.
    """
    if row.get("watcher_went_down"):
        return W_DEAD, ("this lane's own log records `watcher down.` - the "
                        "watcher reported its own exit")
    if row.get("watcher_alive") is False:
        return W_DEAD, ("the pid file names a process the table does not "
                        "hold, so the watcher was taken without logging it")
    if row.get("watcher_alive") is True:
        return W_LIVE, WATCHER_TEXT[W_LIVE][1]
    # `watcher_alive is None`: either the table could not be read or no file
    # names a pid. `_cpu_reading` already distinguishes those and says which
    # in its own words, so they are quoted rather than re-derived.
    why = (row.get("cpu") or {}).get("why")
    return W_UNKNOWN, (why or "this lane's watcher liveness has no authority "
                              "on this board")


def landed(root, lane, queued, offset_hours=None):
    """Which of `queued` already has an entry in `LANE-<lane>.md`.

    SUBTRACTION 2, AND IT IS `src.lanerework`'S CLASSIFIER, NOT A SECOND
    ONE. `brief_id` names the id a filename carries, `headings` parses the
    lane file and `entries_for` compares after normalisation - so `0234b`
    does not answer for `0234`, and `TASK 10` and `TASK 0010` are the same
    brief. Nothing here holds a regex of its own.

    FOUR STATES FOR THE AUTHORITY AND TWO OF THEM ARE NOT AN ANSWER. ABSENT
    and UNREADABLE both give `count=None`, which is UNKNOWN: 0160 recorded
    that reading a missing lane file as "no entry existed" would hand every
    brief a clean verdict off an authority nobody opened. EMPTY is different
    and is an answer - the file exists and says nothing - so its count is 0.
    """
    out = {"state": lanes.ABSENT, "path_shown": None, "landed": [],
           "count": None, "unnamed": []}
    if not root:
        return out
    path = os.path.join(root, "LANE-%s.md" % lane)
    out["path_shown"] = "LANE-%s.md" % lane
    state, text = lanerework._read_text(path)
    out["state"] = state
    if state in (lanes.ABSENT, lanes.UNREADABLE):
        return out
    found = lanerework.headings(text, offset_hours=offset_hours)
    out["count"] = 0
    for name in queued:
        task_id = lanerework.brief_id(name)
        if task_id is None:
            # Not classifiable either way. Named rather than quietly
            # counted as fresh work, and it takes the lane to UNKNOWN.
            out["unnamed"].append(name)
            continue
        entries = lanerework.entries_for(found, task_id)
        if entries:
            out["landed"].append({
                "brief": name, "task_id": task_id,
                "entries": len(entries),
                # THE HEADINGS THEMSELVES, so the claim can be read rather
                # than trusted. A line number is what makes it checkable.
                "lines": [item["line"] for item in entries],
                "headings": [item["text"] for item in entries]})
            out["count"] += 1
    return out


def lane_depth(root, row, floor, offset_hours=None, landing=None):
    """One lane's two depths, and `below_floor` re-derived from the second.

    `landing` is injectable so a test can present a lane file without one on
    disk, the same way the board's process table is handed in. None means
    read it.
    """
    lane = row["lane"]
    raw = row.get("queue_depth")
    # THE NAMES AND THE RAW COUNT ARE ONE READING. `queue_depth` is
    # `len(queued)` in `src.lanes._lane_row` and both travel on the row, so
    # the number this panel prints and the names it classifies cannot be two
    # different listings of one folder. They are only an ANSWER where the
    # folder was read: an empty list under an unreadable queue is not "no
    # briefs", which is why every branch below keys off `raw is None`.
    queued = list(row.get("queued") or [])
    watcher, watcher_why = watcher_reading(row)
    if landing is None:
        landing = landed(root, lane, queued if raw is not None else [],
                         offset_hours=offset_hours)

    inflight = list(row.get("inflight") or [])
    running_state = row.get("running_state")
    # SUBTRACTION 3. A brief in `RUNNING\` with a dead watcher is LOCKED: not
    # queued, not running, and blocking the lane until a person moves it. One
    # with a live watcher is simply running. With liveness UNKNOWN it is
    # neither, and saying so is the whole point.
    locked = inflight if watcher == W_DEAD else []
    running = inflight if watcher == W_LIVE else []
    unplaced = inflight if watcher == W_UNKNOWN else []

    why = []
    if raw is None:
        why.append(U_QUEUE)
    if watcher == W_UNKNOWN:
        why.append(U_WATCHER)
    if landing["count"] is None:
        why.append(U_LANE_FILE)
    if landing["unnamed"]:
        why.append(U_BRIEF_ID)

    # ------------------------------------------------- the consumable number
    #
    # COUNTED, NOT SUBTRACTED. `consumable = raw - landed` can go negative
    # from a double count and would then need a `max(0, ...)` that hides the
    # arithmetic; counting the briefs that survive both subtractions cannot.
    # The identity `consumable + landed == raw` therefore holds by
    # construction and is asserted by this module's own tests.
    if watcher == W_DEAD:
        # THE ONE SHORT CIRCUIT, AND IT IS AN UPPER BOUND RATHER THAN AN
        # EXCEPTION. A watcher that is gone dispatches nothing, so 0 is
        # proven whatever the lane file says; the remaining subtractions
        # could only lower it. Reporting UNKNOWN here would discard the
        # strongest alarm this panel has - and the raw depth is still on the
        # row, so nothing is hidden by it.
        consumable = 0
        consumable_why = ("the watcher is gone, so nothing in this folder "
                          "can start. The raw depth beside this is what is "
                          "waiting for a restart")
    elif why:
        consumable = None
        consumable_why = None
    else:
        landed_names = {item["brief"] for item in landing["landed"]}
        consumable = len([n for n in queued if n not in landed_names])
        consumable_why = None

    # ---------------------------------------------------- the floor, twice
    #
    # The raw verdict is the board's own and is NOT recomputed here: two
    # implementations of one comparison is how the number on this panel and
    # the number in the row above it drift. The re-derived one is this
    # module's answer and it is None wherever either side is missing - a
    # breach is a comparison and a comparison needs both sides.
    below_raw = row.get("below_floor")
    below = (None if consumable is None or floor is None
             else consumable < floor)

    if consumable is None:
        state = S_UNKNOWN
    elif watcher == W_DEAD:
        state = S_STRANDED if (raw or 0) > 0 or locked else S_DEAD_EMPTY
    elif consumable == 0:
        state = S_STARVED
    elif below:
        state = S_BELOW
    else:
        state = S_OK

    return {
        "lane": lane,
        # ------------------------------------------------------ the two depths
        "raw_depth": raw,
        "queue_state": row.get("queue_state"),
        "consumable_depth": consumable,
        "consumable_why": consumable_why,
        "consumable_known": consumable is not None,
        # Named, in order, so the page prints a repair rather than a blank.
        "unknown_because": why,
        # ----------------------------------------------------- the three cuts
        "watcher": watcher,
        "watcher_why": watcher_why,
        "landed": landing["landed"],
        "landed_count": landing["count"],
        "lane_file_state": landing["state"],
        "lane_file_shown": landing["path_shown"],
        "unnamed_briefs": landing["unnamed"],
        "locked": locked,
        "locked_count": len(locked),
        "running": running,
        # In `RUNNING\` with liveness UNKNOWN: neither locked nor running,
        # and it is not folded into either.
        "inflight_unplaced": unplaced,
        "running_state": running_state,
        # --------------------------------------------------------- the floor
        "floor": floor,
        "below_floor": below,
        "below_floor_raw": below_raw,
        # The disagreement, computed rather than left for a reader to spot.
        # True only where both verdicts exist and differ - an UNKNOWN beside
        # a False is not a disagreement, it is an absence.
        "verdicts_disagree": (below is not None and below_raw is not None
                              and below != below_raw),
        "state": state,
    }


def consumable(root=None, now=None, probe=None, samples=None,
               board_data=None, offset_hours=None):
    """The whole panel. `board_data` is the board, read once and passed in.

    The board is the designated authority for liveness and for the floor, and
    it is READ ONCE: a caller that already has it hands it over, and nothing
    here takes a second look at the process table or at `queue/README.md`.
    """
    data = board_data if board_data is not None else lanes.board(
        root=root, now=now, probe=probe, samples=samples)

    out = {
        "state": data.get("state"),
        "root": data.get("root"),
        "root_name": os.path.basename(data.get("root") or "") or None,
        "variable": data.get("variable"),
        "at": data.get("at"),
        "table_read": data.get("table_read"),
        "floor": data.get("floor"),
        "floor_state": data.get("floor_state"),
        "floor_line": data.get("floor_line"),
        "lanes": [],
    }
    if data.get("state") != lanes.PRESENT:
        # NOT an empty table. UNCONFIGURED and ABSENT are the board's own
        # states and they travel through unchanged, because "nobody said
        # where the estate is" must never render as "every lane is fine".
        out.update({"raw_total": None, "raw_lanes": 0,
                    "consumable_total": None, "consumable_lanes": 0,
                    "lane_count": 0, "consumable_complete": False,
                    "unknown_lanes": [], "stranded_lanes": [],
                    "starved_lanes": [], "below_floor_lanes": [],
                    "below_floor_unknown_lanes": [], "disagreeing_lanes": [],
                    "stranded_briefs": 0, "locked_briefs": [],
                    "landed_briefs": 0, "unrecognised": []})
        return out

    if offset_hours is None:
        offset_hours = data.get("local_offset_hours")
    root = data.get("root")
    floor = data.get("floor")
    rows = [lane_depth(root, row, floor, offset_hours=offset_hours)
            for row in data.get("lanes", [])]
    out["lanes"] = rows

    # --------------------------------------------------------- the rollup
    #
    # EVERY TOTAL CARRIES ITS DENOMINATOR, which is `0130`'s discipline and
    # the reason it exists: a sum over the lanes that could be read, printed
    # without saying how many those were, is a confident number about a
    # subset nobody named.
    known_raw = [r for r in rows if r["raw_depth"] is not None]
    known_use = [r for r in rows if r["consumable_depth"] is not None]
    out["lane_count"] = len(rows)
    out["raw_total"] = sum(r["raw_depth"] for r in known_raw)
    out["raw_lanes"] = len(known_raw)
    out["raw_complete"] = len(known_raw) == len(rows)
    out["consumable_total"] = sum(r["consumable_depth"] for r in known_use)
    out["consumable_lanes"] = len(known_use)
    out["consumable_complete"] = len(known_use) == len(rows)
    out["unknown_lanes"] = [r["lane"] for r in rows
                            if r["consumable_depth"] is None]
    out["stranded_lanes"] = [r["lane"] for r in rows
                             if r["state"] == S_STRANDED]
    out["starved_lanes"] = [r["lane"] for r in rows if r["state"] == S_STARVED]
    out["dead_empty_lanes"] = [r["lane"] for r in rows
                               if r["state"] == S_DEAD_EMPTY]
    out["below_floor_lanes"] = [r["lane"] for r in rows
                                if r["below_floor"] is True]
    out["below_floor_unknown_lanes"] = [r["lane"] for r in rows
                                        if r["below_floor"] is None]
    out["disagreeing_lanes"] = [r["lane"] for r in rows
                                if r["verdicts_disagree"]]
    # THE HEADLINE NUMBER OF THE WHOLE PANEL: briefs that exist and cannot
    # start. Sixteen of them at 05:46 and sixteen again at 07:50.
    out["stranded_briefs"] = sum(r["raw_depth"] or 0 for r in rows
                                 if r["watcher"] == W_DEAD)
    out["locked_briefs"] = [{"lane": r["lane"], "brief": name}
                            for r in rows for name in r["locked"]]
    out["landed_briefs"] = sum(r["landed_count"] or 0 for r in rows)
    out["unnamed_briefs"] = [{"lane": r["lane"], "brief": name}
                             for r in rows for name in r["unnamed_briefs"]]
    # A state this module has not named arrives here rather than being filed
    # into whichever bucket came first.
    out["unrecognised"] = sorted({r["state"] for r in rows
                                  if r["state"] not in STATE_TEXT})
    return out


def describe(data=None):
    """The panel as text, for a terminal. Same reader, same refusals."""
    data = data if data is not None else consumable()
    if data["state"] == lanes.UNCONFIGURED:
        return ("UNCONFIGURED: set %s to the lane estate's directory. That is "
                "NOT 'no lanes' and not 'every lane is fine'."
                % data.get("variable"))
    if data["state"] == lanes.ABSENT:
        return ("ABSENT: %s names %s, which is not a directory."
                % (data.get("variable"), data.get("root")))

    out = ["CONSUMABLE QUEUE DEPTH   estate=%s   floor=%s (%s)"
           % (data["root_name"],
              data["floor"] if data["floor"] is not None else "UNKNOWN",
              data["floor_state"]),
           "",
           "%-12s %5s %6s %-9s %7s %7s %-15s %s"
           % ("lane", "raw", "usable", "watcher", "landed", "locked",
              "state", "below floor (usable / raw)"),
           "-" * 104]
    for row in data["lanes"]:
        out.append("%-12s %5s %6s %-9s %7s %7s %-15s %s / %s"
                   % (row["lane"],
                      _n(row["raw_depth"]), _n(row["consumable_depth"]),
                      row["watcher"], _n(row["landed_count"]),
                      row["locked_count"], STATE_TEXT[row["state"]][0]
                      if row["state"] in STATE_TEXT else row["state"],
                      _n(row["below_floor"]), _n(row["below_floor_raw"])))
    out.append("-" * 104)
    out.append("RAW %s across %d of %d lanes.  CONSUMABLE %s across %d of %d."
               % (_n(data["raw_total"]), data["raw_lanes"], data["lane_count"],
                  _n(data["consumable_total"]), data["consumable_lanes"],
                  data["lane_count"]))
    out.append("%d brief(s) queued behind a dead watcher and unable to start."
               % data["stranded_briefs"])
    if data["stranded_lanes"]:
        out.append("  STRANDED (restart the watcher): %s"
                   % ", ".join(data["stranded_lanes"]))
    if data["starved_lanes"]:
        out.append("  STARVED (write a brief): %s"
                   % ", ".join(data["starved_lanes"]))
    if data["locked_briefs"]:
        out.append("  LOCKED in RUNNING\\ behind a dead watcher - move by "
                   "hand, do not clear from code: %s"
                   % ", ".join("%s/%s" % (item["lane"], item["brief"])
                               for item in data["locked_briefs"]))
    if data["unknown_lanes"]:
        out.append("  CONSUMABLE UNKNOWN: %s" % ", ".join(data["unknown_lanes"]))
    if data["disagreeing_lanes"]:
        out.append("  THE TWO FLOOR VERDICTS DISAGREE on: %s. The raw count "
                   "is the one the floor was being enforced against."
                   % ", ".join(data["disagreeing_lanes"]))
    return "\n".join(out)


def _n(value):
    """UNKNOWN for None. Never a blank and never a zero."""
    return "UNKNOWN" if value is None else str(value)


if __name__ == "__main__":                                  # pragma: no cover
    print(describe())
