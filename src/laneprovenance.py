#!/usr/bin/env python3
"""Where every number on the lane pages comes from, and whether it can lie.

WHY THIS MODULE EXISTS. `src/lanes.py`, `src/floorledger.py` and
`src/exitcriteria.py` between them hand the three admin pages **575 distinct
figure paths**, measured 2026-10-16. Each descends from one of a small number
of files on this machine, and at least one of those files is known to carry
positively false rows: a `DONE\\` filename. Nobody had checked which figure
reads which source, so nobody could answer the only question that matters
after a bad night - *is this number counting tasks that never ran?*

THE ANSWER THIS MODULE MAKES CHECKABLE, rather than arguable. Every path is
matched against a registry of sources. A path matching no entry is
**UNCOVERED**, which renders UNKNOWN and is named - never left off the table
and never allowed to keep printing its old value with a footnote. And a
SOURCE that matches no path is reported as matching none, because "the board
does not read the DONE folder" and "the rule that looks for DONE-folder reads
is broken" are different facts and a dropped row cannot tell them apart.

WHAT IT WILL NOT DO. It writes nothing. It reads `queue\\` and `logs\\` and
it creates, moves, renames and deletes nothing in either - the contaminated
`DONE\\` entries of 2026-10-16 are evidence held for another lane and this
module reports them where they stand. It reaches no provider and opens no
socket.

THE RULE IT IS BUILT AROUND, which is the estate's invariant 0 in this
module's terms: a figure whose provenance cannot be established is UNKNOWN,
and UNKNOWN is never clean, never zero and never "probably the log".
"""
import os
import re

from src import lanes

# --------------------------------------------------------------- the sources
#
# One entry per FILE OR TABLE a figure can descend from. The split is by what
# is read, not by who reads it: the `.out` file appears three times because
# its TEXT, its SIZE and its MTIME are three different authorities with three
# different failure modes, and the estate has been misled by two of them.

#: `CONTINUITY.md` §3 names this as the authority for its question.
LISTED = "listed"
#: §3 names it explicitly as something that is NOT the authority - the DONE
#: filename, a non-empty `.out`, an empty `RUNNING\`, a LANE file's mtime.
#: Using one of these needs a reason, and the reason is carried here.
REFUSED_BY_LIST = "refused_by_list"
#: §3 says nothing about it either way.
NOT_LISTED = "not_listed"

AUTHORITY_TEXT = {
    LISTED: ("ON THE LIST",
             "named in CONTINUITY.md section 3 as the authority for its "
             "question"),
    REFUSED_BY_LIST: ("REFUSED BY THE LIST",
                      "section 3 names this source explicitly as something "
                      "that is NOT the authority. Every figure reading it "
                      "carries the reason it is read anyway"),
    NOT_LISTED: ("NOT ON THE LIST",
                 "section 3 neither designates nor refuses it. That is not "
                 "permission: it means nobody has ruled on it"),
}

S_WATCHER_LOG = "watcher_log"
S_OUT_TEXT = "out_text"
S_OUT_BYTES = "out_bytes"
S_OUT_MTIME = "out_mtime"
S_DONE_PATH = "done_path"
S_DONE_LISTING = "done_listing"
S_QUEUE_LISTING = "queue_listing"
S_PROCESS_TABLE = "process_table"
S_CPU_DELTA = "cpu_delta"
S_PID_FILE = "pid_file"
S_SUITE_LOCK = "suite_lock"
S_LOCK_DIR_LISTING = "lock_dir_listing"
S_LOCK_QUEUE = "lock_queue"
S_LANE_FILE_TEXT = "lane_file_text"
S_LANE_FILE_MTIME = "lane_file_mtime"
S_QUEUE_README = "queue_readme"
S_OPS_DOCUMENTS = "ops_documents"
S_OWN_LEDGER = "own_ledger"
S_MACHINE_CLOCK = "machine_clock"
S_CONSTANT = "constant"
S_SOURCE_PROSE = "source_prose"
S_DERIVED = "derived"
S_ENVIRONMENT = "environment"

SOURCES = {
    S_WATCHER_LOG: {
        "label": "a `logs\\watcher-<lane>.log` line",
        "authority": LISTED,
        "quote": "A task is finished only when logs\\watcher-<lane>.log holds "
                 "its DONE line and that line reads exit0",
        "can_be_false": True,
        "why": "TWO WAYS, BOTH MEASURED. (1) LINES GO MISSING SILENTLY: the "
               "watcher's own `Log` helper swallows a failed `Add-Content`, "
               "so an absent line is not evidence an event did not happen - "
               "`watcher-glm-b.log` holds 77 records and ZERO `MOVED` lines "
               "while both of its 2026-10-16 DONE entries sit in `DONE\\`. "
               "(2) THE LINE IS TRUE ABOUT THE EXIT CODE AND FALSE ABOUT THE "
               "WORK: `DONE <task> -> exit1` is what the watcher writes for a "
               "task that ran and failed AND for one the provider refused, "
               "because it has no third word. The log is still the best "
               "authority available; it is not an infallible one",
    },
    S_OUT_TEXT: {
        "label": "the TEXT of a task's `.out` file",
        "authority": LISTED,
        "quote": "On a GLM lane, a .out of 713 bytes - or 559 if the refusal "
                 "landed before the error line - is the 429, not a report",
        "can_be_false": True,
        "why": "IT HOLDS THE SESSION'S FINAL OUTPUT AND NOT ITS HISTORY. "
               "`claude -p` emits its result when it ends, so a session that "
               "worked for 59 minutes and then hit a 429 leaves a file "
               "BYTE-FOR-BYTE INDISTINGUISHABLE from one refused at dispatch. "
               "Measured 2026-10-16: three of the eight refusals ran 24.4, "
               "59.1 and 59.3 minutes before their refusal arrived, and all "
               "eight `.out` files carry the 429 and nothing else. The text "
               "proves what the session LAST said. It does not prove the "
               "session did nothing",
    },
    S_OUT_BYTES: {
        "label": "the SIZE in bytes of a task's `.out` file",
        "authority": REFUSED_BY_LIST,
        "quote": "A .out file fills only at the end; 0 bytes mid-run is "
                 "normal and 58 minutes at 0 bytes happened on a healthy task",
        "can_be_false": True,
        "why": "`cmd.exe` creates the file at START and nothing is flushed "
               "into it until the task ends, so a working lane's file is 0 "
               "bytes and a dead one's is too. It is read here ONLY for a "
               "CLOSED task, where 0 bytes means the output was lost, and "
               "ONLY as a figure beside the text - never as the thing that "
               "classifies. 713 bytes is a SIGNATURE and not a proof: the "
               "eight refusals were all 713 bytes and all `exit1`, and a "
               "detector built on either coincidence would fire on the next "
               "ordinary failure",
    },
    S_OUT_MTIME: {
        "label": "the MTIME of a task's `.out` file",
        "authority": NOT_LISTED,
        "quote": None,
        "can_be_false": True,
        "why": "the file is created at START and written at the end, so its "
               "mtime dates the END of a run that produced output and the "
               "START of one that produced none - two opposite meanings with "
               "no field to tell them apart. NOT READ BY ANY FIGURE, and "
               "listed so that a future reader can see it was refused rather "
               "than overlooked",
    },
    S_DONE_PATH: {
        "label": "`os.path.exists` / `getsize` on ONE `DONE\\` path the "
                 "watcher's own line names",
        "authority": REFUSED_BY_LIST,
        "quote": "As of 02:00 a DONE\\ filename can be positively false, not "
                 "merely uninformative",
        "can_be_false": True,
        "why": "READ BECAUSE `Move-Item` PRESERVES BYTES, which makes the "
               "copy in `DONE\\` the brief itself and a REFUSED verdict "
               "actionable instead of a post-mortem. The folder is never "
               "LISTED and no name is ever trusted: the name is BUILT from "
               "the watcher's own `$stamp`, suffix and task, and only then is "
               "the path tested. So a planted file moves nothing - unless it "
               "is planted at exactly that derived name, which is the one "
               "way this source can still lie, and the control that proves "
               "it is `a_file_planted_at_the_derived_name_is_believed`",
    },
    S_DONE_LISTING: {
        "label": "a LISTING of a `queue\\<lane>\\DONE\\` folder",
        "authority": REFUSED_BY_LIST,
        "quote": "Not a filename in DONE\\, not an empty RUNNING\\, not a "
                 "non-empty .out",
        "can_be_false": True,
        "why": "ITS COUNT IS WRONG IN BOTH DIRECTIONS AND IT HAS FOUR "
               "AUTHORS. Measured 2026-10-16 across all seven lanes: 152 "
               "files, of which 131 trace to a watcher line and 21 DO NOT - "
               "12 closed by a person as `HANDCLOSED`, 2 watcher entries a "
               "person RENAMED to `TIMEOUT-but-complete`, 5 copies a LANE "
               "SESSION wrote itself when the watcher's move was refused, "
               "and 2 of no established shape at all. Nine of the 131 are "
               "`exit1` for briefs the provider refused. NO FIGURE ON ANY OF "
               "THE THREE PAGES READS THIS SOURCE - which is the result of "
               "this task, and it is reported as a measured zero rather than "
               "as an absent row",
    },
    S_QUEUE_LISTING: {
        "label": "a `*.md` listing of `queue\\<lane>\\` or its `RUNNING\\`",
        "authority": REFUSED_BY_LIST,
        "quote": "Not a filename in DONE\\, not an empty RUNNING\\",
        "can_be_false": True,
        "why": "it answers what the watcher will take next, which is exactly "
               "what it is read for, and it says nothing about whether a "
               "brief in `RUNNING\\` has an owner. A stranded brief looks "
               "in-flight for as long as nobody moves it, which is the STUCK "
               "state and is why the board crosses this with the process "
               "table rather than believing it",
    },
    S_PROCESS_TABLE: {
        "label": "the OS process table (`Win32_Process` / `/proc`)",
        "authority": LISTED,
        "quote": "A watcher is dead when its pid is gone from the process "
                 "table, which only the laptop can see",
        "can_be_false": True,
        "why": "Windows REUSES a pid, and a process whose real parent has "
               "exited keeps a parent pid that may now name something else, "
               "so lineage is a heuristic and is reported as one. A table "
               "that cannot be read makes every liveness answer UNKNOWN and "
               "never idle",
    },
    S_CPU_DELTA: {
        "label": "CPU seconds under the watcher's process, sampled twice",
        "authority": LISTED,
        "quote": "A task is alive by the CPU time of its child process, "
                 "sampled twice",
        "can_be_false": False,
        "why": "CPU time that moves cannot be faked by a stuck process, which "
               "is why it is the authority rather than a spinner or an mtime. "
               "The failure mode is ABSENCE and not falsehood: the samples "
               "live in memory for the life of the process, so a first page "
               "load has no delta and says so instead of showing one",
    },
    S_PID_FILE: {
        "label": "`logs\\watcher-<lane>.pid`",
        "authority": NOT_LISTED,
        "quote": None,
        "can_be_false": True,
        "why": "the watcher removes it on a CLEAN exit, so ABSENT means no "
               "watcher is registered and not that none is running - and a "
               "hard kill leaves the file behind with a dead pid in it. It is "
               "read only to find a root to walk from, and the walk's own "
               "verdict is what is reported",
    },
    S_SUITE_LOCK: {
        "label": "the BYTES of the machine-wide `work\\suite.lock`",
        "authority": NOT_LISTED,
        "quote": None,
        "can_be_false": True,
        "why": "IT IS A FACT ABOUT A FILE AND NOT ABOUT THE MACHINE. The pid "
               "it names is whatever the holder wrote at acquire time, and "
               "Windows REUSES a pid - so a lock outliving its holder can "
               "name somebody else's live process, which would read as HELD. "
               "That is why the pid is crossed with the process table and "
               "never believed alone. Its `started_at` is trustworthy by "
               "construction and was not always: it recorded the LAUNCH "
               "until 2026-10-02, overstating one hold by 39 minutes, which "
               "is why `queued_at` is now carried beside it",
    },
    S_LOCK_DIR_LISTING: {
        "label": "the LISTING of the directory holding `suite.lock`",
        "authority": NOT_LISTED,
        "quote": None,
        "can_be_false": True,
        "why": "THE ONLY AUTHORITY THAT CAN PROVE A LOCK FREE, and it is a "
               "different question from reading the file. `os.path.exists` "
               "and `suitelock.read` both answer the same thing for 'not "
               "there' and 'cannot be reached', and those two must not "
               "merge: the first is FREE and the second is UNKNOWN. A "
               "listing that SUCCEEDS and lacks the name proves absence; a "
               "listing that fails proves nothing. It can still be false "
               "about the next instant - a lock can be taken immediately "
               "after it is read",
    },
    S_LOCK_QUEUE: {
        "label": "the LISTING of `suite.lock.queue`, the ticket directory",
        "authority": NOT_LISTED,
        "quote": None,
        "can_be_false": True,
        "why": "a ticket is a waiter's CLAIM and not a running suite, and "
               "the directory holds the tickets of dead waiters until "
               "`acquire` walks past and prunes them - this reader does NOT "
               "prune, because an instrument that edits what it measures is "
               "not one, so a dead ticket is counted and named rather than "
               "removed. A file that is not one of ours is counted as "
               "foreign and never interpreted",
    },
    S_LANE_FILE_TEXT: {
        "label": "the PROSE of `LANE-<lane>.md`",
        "authority": NOT_LISTED,
        "quote": None,
        "can_be_false": True,
        "why": "THE SCOPE IS A HEURISTIC. A lane file has no machine-readable "
               "entry boundary, so the last `## ` heading can be narrower "
               "than the last entry, and the owed-gate scan matches a fixed "
               "set of phrases: NO MARKER IS NOT 'nothing is owed', it is 'no "
               "phrase this scan knows was found'. The page is required to "
               "say so wherever it shows this",
    },
    S_LANE_FILE_MTIME: {
        "label": "the MTIME of `LANE-<lane>.md`",
        "authority": REFUSED_BY_LIST,
        "quote": "A lane's work is NOT proven landed by its LANE file's mtime",
        "can_be_false": True,
        "why": "an append moves it and so does a typo, and `Move-Item` "
               "preserving mtime is what makes the same reasoning invalid in "
               "`DONE\\`. NOT READ BY ANY FIGURE. It is listed because the "
               "watcher's own NOWORK test is 'did this file grow', so a "
               "reader may reasonably expect the page to use it - and the "
               "page does not",
    },
    S_QUEUE_README: {
        "label": "the floor line in `queue\\README.md`",
        "authority": NOT_LISTED,
        "quote": None,
        "can_be_false": True,
        "why": "it is the operator's own prose with no interlock. The figure "
               "it feeds is UNKNOWN and NEVER 3 when the line cannot be read, "
               "because assuming 3 is the hand-kept denominator this estate "
               "has a failure family for: the operator raises the floor, the "
               "page keeps comparing against the old number, and every lane "
               "reads compliant",
    },
    S_OPS_DOCUMENTS: {
        "label": "a verdict table in a `resonate-ops\\*.md` authority document",
        "authority": NOT_LISTED,
        "quote": None,
        "can_be_false": True,
        "why": "a document states what was true when it was measured and "
               "carries no interlock against the thing it measured, so it "
               "goes STALE silently; two documents can answer one question "
               "differently, which renders CONTESTED rather than averaged; "
               "and a verdict can be WITHDRAWN in an appendix the body still "
               "contradicts",
    },
    S_OWN_LEDGER: {
        "label": "`runtime\\floor-breach-ledger.jsonl`, a file of our own",
        "authority": NOT_LISTED,
        "quote": None,
        "can_be_false": True,
        "why": "IT ONLY HOLDS ROWS FOR MOMENTS SOMEBODY LOOKED. The page is "
               "the sampler, so a gap in it is a gap in the watching and not "
               "a quiet period - which is why coverage is computed and a hole "
               "renders UNKNOWN instead of being interpolated across",
    },
    S_MACHINE_CLOCK: {
        "label": "this machine's clock and its UTC offset at `now`",
        "authority": NOT_LISTED,
        "quote": None,
        "can_be_false": True,
        "why": "every elapsed figure and every 'since' figure rests on it, "
               "and nothing here checks it against an external clock. The "
               "offset is MEASURED at the instant being converted rather "
               "than written down as a constant, which is what keeps it right "
               "across a DST change - and the provider's own reset string "
               "carries no zone at all, so the two-clock conversion is shown "
               "with both offsets named",
    },
    S_CONSTANT: {
        "label": "a published constant in this repository's source",
        "authority": NOT_LISTED,
        "quote": None,
        "can_be_false": True,
        "why": "it cannot be misread, and it CAN be wrong about the estate: a "
               "running watcher keeps the constant it loaded with, so a value "
               "edited on disk since is not the one in force. The one figure "
               "where this bit - the lane timeout - is read from the lane's "
               "own `watcher up` line instead, and says so",
    },
    S_SOURCE_PROSE: {
        "label": "a glossary sentence written in this repository's source",
        "authority": NOT_LISTED,
        "quote": None,
        "can_be_false": True,
        "why": "AND ONE OF THEM WAS. `OUTCOME_TEXT[refused]` asserted 'the "
               "provider rejected the request, so this task NEVER RAN' on "
               "every refusal row. Three of the eight refusals of 2026-10-16 "
               "ran 24.4, 59.1 and 59.3 minutes, which the same module "
               "already computed from its own START and DONE lines. A "
               "glossary is a CLAIM and is checkable against the data beside "
               "it; this one was not checked for sixteen hours",
    },
    S_DERIVED: {
        "label": "arithmetic over other sources on this table",
        "authority": NOT_LISTED,
        "quote": None,
        "can_be_false": True,
        "why": "it inherits every falsehood of its inputs and adds one of its "
               "own - a derivation can be sound and still be read as a "
               "measurement. Measured 2026-10-16: `glm`'s utilisation renders "
               "104.8%, which is arithmetically impossible for one lane and "
               "is the overlap of two START..DONE intervals the watcher wrote "
               "for one worktree",
    },
    S_ENVIRONMENT: {
        "label": "an environment variable, or the absence of one",
        "authority": NOT_LISTED,
        "quote": None,
        "can_be_false": True,
        "why": "`LANE_OPS_DIR` unset makes the whole board UNCONFIGURED, "
               "which the page states and names - it is not 'there are no "
               "lanes' and must never render as a clean empty table",
    },
}


# ------------------------------------------- what `exit1` is silently merging
#
# The brief's question 3, as a field. `exit1` is one word for three states and
# the watcher has no fourth: a task that ran and failed, a task the provider
# refused, and a brief a person closed by hand. For each figure, which of them
# is it adding together?

M_NOT_A_COUNT = "not_a_count"
M_KEPT_APART = "kept_apart"
M_RAN_AND_REFUSED = "ran_and_refused"
M_REFUSAL_SUBSTATES = "refusal_substates"
M_HANDCLOSED_INVISIBLE = "handclosed_invisible"

MERGE_TEXT = {
    M_NOT_A_COUNT: (
        "not a count",
        "a single row's own field, or a state word. It carries whatever its "
        "one task was and merges nothing with anything"),
    M_KEPT_APART: (
        "kept apart",
        "this figure counts one of the three and only that one. Separating "
        "them would not change it"),
    M_RAN_AND_REFUSED: (
        "RAN + REFUSED",
        "a task that ran and failed and a task the provider refused are added "
        "together here. The DONE suffix is the same word for both"),
    M_REFUSAL_SUBSTATES: (
        "REFUSED AT DISPATCH + CUT OFF MID-RUN",
        "a refusal whose 429 arrived seconds after START and one whose 429 "
        "arrived 59 minutes after START are added together here. Their `.out` "
        "files are indistinguishable; their elapsed times are not"),
    M_HANDCLOSED_INVISIBLE: (
        "HAND-CLOSED: invisible, not merged",
        "a brief a person closed by hand has no watcher line, so it is not "
        "added into this figure - it is absent from it. 21 of the estate's "
        "152 `DONE\\` files are in that position, and a reader who takes this "
        "figure for the number of closed briefs is short by that many"),
}


# ----------------------------------------------------------------- the figures
#
# One entry per PATH PATTERN, not per leaf: a subtree whose every leaf has one
# source gets one row, ending `.*`. `[]` stands for a list index. The registry
# is checked against the LIVE paths by `coverage`, so a pattern that stops
# matching - or a figure added with no row here - is a test failure and not a
# silently unsourced number on a page.

#: `(pattern, source_key, merges, note)`. `note` is "" where the source's own
#: `why` says everything; it exists for the figures that need a sentence of
#: their own.
FIGURES = (
    # ---------------------------------------------------- the board's frame
    ("lane_board.state", S_ENVIRONMENT, M_NOT_A_COUNT, ""),
    ("lane_board.root", S_ENVIRONMENT, M_NOT_A_COUNT, ""),
    ("lane_board.root_name", S_ENVIRONMENT, M_NOT_A_COUNT, ""),
    ("lane_board.variable", S_CONSTANT, M_NOT_A_COUNT, ""),
    ("lane_board.at", S_MACHINE_CLOCK, M_NOT_A_COUNT, ""),
    ("lane_board.table_read", S_PROCESS_TABLE, M_NOT_A_COUNT, ""),
    ("lane_board.lane_count", S_QUEUE_LISTING, M_NOT_A_COUNT,
     "the UNION of the queue folders and the watcher logs, so a lane with "
     "only one of the two is still a row"),
    ("lane_board.lanes", S_QUEUE_LISTING, M_NOT_A_COUNT, ""),
    # ------------------------------------------------ one lane, the log half
    ("lane_board.lanes[].lane", S_QUEUE_LISTING, M_NOT_A_COUNT, ""),
    ("lane_board.lanes[].found_in", S_QUEUE_LISTING, M_NOT_A_COUNT, ""),
    ("lane_board.lanes[].status", S_WATCHER_LOG, M_NOT_A_COUNT,
     "from the ORDER of the newest START against the newest DONE, never from "
     "the last line - a task's own stdout is appended after its DONE line"),
    ("lane_board.lanes[].records", S_WATCHER_LOG, M_RAN_AND_REFUSED,
     "every record in the log, so the refusals of 2026-10-16 are in it"),
    ("lane_board.lanes[].log_state", S_WATCHER_LOG, M_NOT_A_COUNT, ""),
    ("lane_board.lanes[].log_truncated", S_WATCHER_LOG, M_NOT_A_COUNT, ""),
    ("lane_board.lanes[].last_done_line", S_WATCHER_LOG, M_NOT_A_COUNT,
     "VERBATIM. The line is the evidence, and a summary of it would be the "
     "misreport again in different words"),
    ("lane_board.lanes[].last_done_task", S_WATCHER_LOG, M_NOT_A_COUNT, ""),
    ("lane_board.lanes[].last_done_suffix", S_WATCHER_LOG, M_RAN_AND_REFUSED,
     "`exit1` here is the word for both, and the board's own last-DONE column "
     "cannot tell a reader which it was. The classified row below it can"),
    ("lane_board.lanes[].last_done_at", S_WATCHER_LOG, M_NOT_A_COUNT, ""),
    ("lane_board.lanes[].last_start_task", S_WATCHER_LOG, M_NOT_A_COUNT, ""),
    ("lane_board.lanes[].last_start_at", S_WATCHER_LOG, M_NOT_A_COUNT, ""),
    ("lane_board.lanes[].last_event_kind", S_WATCHER_LOG, M_NOT_A_COUNT, ""),
    ("lane_board.lanes[].last_event_at", S_WATCHER_LOG, M_NOT_A_COUNT, ""),
    ("lane_board.lanes[].done_short", S_SOURCE_PROSE, M_NOT_A_COUNT, ""),
    ("lane_board.lanes[].done_meaning", S_SOURCE_PROSE, M_NOT_A_COUNT, ""),
    ("lane_board.lanes[].since_seconds", S_DERIVED, M_NOT_A_COUNT, ""),
    ("lane_board.lanes[].log_silent_seconds", S_DERIVED, M_NOT_A_COUNT, ""),
    ("lane_board.lanes[].log_has_gone_quiet", S_DERIVED, M_NOT_A_COUNT, ""),
    ("lane_board.lanes[].heartbeat_seconds", S_CONSTANT, M_NOT_A_COUNT, ""),
    ("lane_board.lanes[].timeout_minutes", S_WATCHER_LOG, M_NOT_A_COUNT,
     "from this lane's own `watcher up` line and NOT from the script on "
     "disk: a running watcher keeps the constant it loaded with"),
    ("lane_board.lanes[].timeout_from", S_SOURCE_PROSE, M_NOT_A_COUNT, ""),
    # --------------------------------------------- one lane, the liveness half
    ("lane_board.lanes[].watcher_pid_state", S_PID_FILE, M_NOT_A_COUNT, ""),
    ("lane_board.lanes[].watcher_pid", S_PID_FILE, M_NOT_A_COUNT, ""),
    ("lane_board.lanes[].watcher_alive", S_PROCESS_TABLE, M_NOT_A_COUNT, ""),
    ("lane_board.lanes[].watcher_image_ok", S_PROCESS_TABLE, M_NOT_A_COUNT, ""),
    ("lane_board.lanes[].watcher_went_down", S_WATCHER_LOG, M_NOT_A_COUNT,
     "the LOG's own claim, never set by inference, so a reader is never told "
     "the watcher logged something it did not"),
    ("lane_board.lanes[].watcher_inferred_down", S_DERIVED, M_NOT_A_COUNT, ""),
    ("lane_board.lanes[].cpu.root_pid", S_PID_FILE, M_NOT_A_COUNT, ""),
    ("lane_board.lanes[].cpu.pids", S_PROCESS_TABLE, M_NOT_A_COUNT, ""),
    ("lane_board.lanes[].cpu.pids[]", S_PROCESS_TABLE, M_NOT_A_COUNT, ""),
    ("lane_board.lanes[].cpu.count", S_PROCESS_TABLE, M_NOT_A_COUNT, ""),
    ("lane_board.lanes[].cpu.unmeasured", S_PROCESS_TABLE, M_NOT_A_COUNT, ""),
    ("lane_board.lanes[].cpu.unmeasured[]", S_PROCESS_TABLE, M_NOT_A_COUNT, ""),
    ("lane_board.lanes[].cpu.seconds", S_CPU_DELTA, M_NOT_A_COUNT, ""),
    ("lane_board.lanes[].cpu.delta_seconds", S_CPU_DELTA, M_NOT_A_COUNT, ""),
    ("lane_board.lanes[].cpu.wall_seconds", S_MACHINE_CLOCK, M_NOT_A_COUNT, ""),
    ("lane_board.lanes[].cpu.why", S_SOURCE_PROSE, M_NOT_A_COUNT, ""),
    ("lane_board.lanes[].verdict", S_DERIVED, M_NOT_A_COUNT,
     "the log crossed with the process table. Where they disagree it names "
     "the disagreement; where one is missing it is UNCROSSED and never the "
     "surviving one reported as though it were both"),
    ("lane_board.lanes[].verdict_label", S_SOURCE_PROSE, M_NOT_A_COUNT, ""),
    ("lane_board.lanes[].verdict_why", S_SOURCE_PROSE, M_NOT_A_COUNT, ""),
    # ------------------------------------------- one lane, the queue half
    ("lane_board.lanes[].queue_state", S_QUEUE_LISTING, M_NOT_A_COUNT, ""),
    ("lane_board.lanes[].queue_depth", S_QUEUE_LISTING, M_HANDCLOSED_INVISIBLE,
     "briefs WAITING, so a hand-closed one has already left it. A person who "
     "closes six briefs drops this figure by six with no record anywhere the "
     "page reads"),
    ("lane_board.lanes[].queued", S_QUEUE_LISTING, M_HANDCLOSED_INVISIBLE,
     "the names `queue_depth` is the length of - one listing, so a count and "
     "a name-set on this page cannot be two readings of one folder. Only an "
     "answer where `queue_state` is PRESENT: an empty list under an "
     "unreadable queue is not 'no briefs'"),
    ("lane_board.lanes[].queued[]", S_QUEUE_LISTING,
     M_HANDCLOSED_INVISIBLE, ""),
    ("lane_board.lanes[].next_up", S_QUEUE_LISTING, M_NOT_A_COUNT,
     "ordered the way `Sort-Object Name` orders, so the name shown is the one "
     "the watcher will actually take"),
    ("lane_board.lanes[].running_state", S_QUEUE_LISTING, M_NOT_A_COUNT, ""),
    ("lane_board.lanes[].inflight", S_QUEUE_LISTING, M_NOT_A_COUNT, ""),
    ("lane_board.lanes[].inflight[]", S_QUEUE_LISTING, M_NOT_A_COUNT, ""),
    ("lane_board.lanes[].owed.*", S_LANE_FILE_TEXT, M_NOT_A_COUNT, ""),
    # ------------------------------- one lane, the clock it is running against
    #
    # The timeout, the elapsed time and the remainder have THREE DIFFERENT
    # sources and they fail independently, so they get three rows rather than
    # one subtree. A reader who could not tell which side of `remaining` was
    # missing would be back to one empty cell for every cause.
    ("lane_board.lanes[].log_path_shown", S_ENVIRONMENT, M_NOT_A_COUNT,
     "the TAIL of the path, never the absolute one, so an UNKNOWN timeout "
     "names the file to go and read without printing anybody's home "
     "directory"),
    ("lane_board.lanes[].timeout_state", S_WATCHER_LOG, M_NOT_A_COUNT,
     "WHICH of the three UNKNOWNs it is: no `watcher up` line, an `up` line "
     "with no timeout= field, or an `up` line a newer `watcher down.` has "
     "superseded. Three different repairs"),
    ("lane_board.lanes[].clock.running_state", S_QUEUE_LISTING,
     M_NOT_A_COUNT, ""),
    ("lane_board.lanes[].clock.brief", S_QUEUE_LISTING, M_NOT_A_COUNT,
     "WHICH brief the clock is about, from the RUNNING\\ listing - a source "
     "section 3 refuses as an authority on whether that brief still has an "
     "owner, which is why the elapsed figure beside it comes from the log"),
    ("lane_board.lanes[].clock.extra_briefs", S_QUEUE_LISTING,
     M_NOT_A_COUNT,
     "a second file in RUNNING\\ is a defect in itself: the watcher runs one "
     "task at a time, so it is a hand-placed brief or an uncleaned orphan"),
    ("lane_board.lanes[].clock.extra_briefs[]", S_QUEUE_LISTING,
     M_NOT_A_COUNT, ""),
    ("lane_board.lanes[].clock.timeout_minutes", S_WATCHER_LOG,
     M_NOT_A_COUNT,
     "this lane's OWN cap, from its own `watcher up` line. Measured "
     "2026-10-16 06:38: four of seven lanes were running 90m while "
     "tools/lane_watcher.ps1 on disk said 150m"),
    ("lane_board.lanes[].clock.timeout_state", S_WATCHER_LOG,
     M_NOT_A_COUNT, ""),
    ("lane_board.lanes[].clock.started_at", S_WATCHER_LOG, M_NOT_A_COUNT,
     "the `START <brief>` line naming THIS brief, not the lane's newest "
     "START - a lane whose RUNNING\\ brief is an orphan has both"),
    ("lane_board.lanes[].clock.elapsed_seconds", S_DERIVED, M_NOT_A_COUNT,
     "that START stamp against this machine's clock, so it inherits the "
     "clock's own unverified offset"),
    ("lane_board.lanes[].clock.elapsed_state", S_DERIVED, M_NOT_A_COUNT,
     "including the reading that is NOT an UNKNOWN: a DONE line newer than "
     "the START means the clock has stopped and the file in RUNNING\\ is a "
     "leftover"),
    ("lane_board.lanes[].clock.remaining_seconds", S_DERIVED, M_NOT_A_COUNT,
     "the cap minus the elapsed time, and None whenever either side is "
     "UNKNOWN. It is never negative: past the cap is its own reading"),
    ("lane_board.lanes[].clock.remaining_state", S_DERIVED, M_NOT_A_COUNT,
     "KNOWN, PAST or UNKNOWN. PAST is a state and never a clamped zero - a "
     "zero there would be the most dangerous cell on this page"),
    ("lane_board.lanes[].clock.over_seconds", S_DERIVED, M_NOT_A_COUNT,
     "how far past the cap, which is only set in the PAST state. Measured "
     "live 2026-10-16 06:38 at 249 minutes on one lane"),
    ("lane_board.lanes[].clock.near_timeout", S_DERIVED, M_NOT_A_COUNT,
     "inside the window in which the timeout chain fires. None - never "
     "False - when the remainder is UNKNOWN"),
    ("lane_board.lanes[].clock.near_window_seconds", S_CONSTANT,
     M_NOT_A_COUNT,
     "ten minutes, from the brief, and the one figure here that is a "
     "published constant rather than a measurement"),
    ("lane_board.lanes[].clock.timeout_label", S_SOURCE_PROSE,
     M_NOT_A_COUNT, ""),
    ("lane_board.lanes[].clock.timeout_why", S_SOURCE_PROSE,
     M_NOT_A_COUNT, ""),
    ("lane_board.lanes[].clock.elapsed_label", S_SOURCE_PROSE,
     M_NOT_A_COUNT, ""),
    ("lane_board.lanes[].clock.elapsed_why", S_SOURCE_PROSE,
     M_NOT_A_COUNT, ""),
    # ------------------------------------------- one lane, starvation and floor
    ("lane_board.lanes[].median_task_minutes", S_WATCHER_LOG,
     M_RAN_AND_REFUSED,
     "the median over every START paired with a DONE, so the eight refusals "
     "of 2026-10-16 are IN IT - and three of them at 24 to 59 minutes pull it "
     "UP while the five short ones pull it down"),
    ("lane_board.lanes[].starvation_minutes", S_DERIVED, M_RAN_AND_REFUSED,
     "depth x median, so it inherits the median's contamination"),
    ("lane_board.lanes[].utilisation.*", S_DERIVED, M_RAN_AND_REFUSED,
     "busy is a paired START..DONE interval clipped to the window, and a "
     "refusal's interval counts as busy. `glm` renders 104.8%, which is "
     "arithmetically impossible for one lane"),
    ("lane_board.lanes[].below_floor", S_DERIVED, M_NOT_A_COUNT,
     "a comparison, and None when EITHER side is unknown - an unreadable "
     "queue is not a breach and is not compliance either"),
    ("lane_board.lanes[].floor", S_QUEUE_README, M_NOT_A_COUNT, ""),
    ("lane_board.lanes[].is_stuck", S_DERIVED, M_NOT_A_COUNT, ""),
    ("lane_board.lanes[].stuck_undecidable", S_DERIVED, M_NOT_A_COUNT, ""),
    ("lane_board.lanes[].refusal_loop", S_WATCHER_LOG, M_NOT_A_COUNT, ""),
    ("lane_board.lanes[].refusal_loop.*", S_WATCHER_LOG, M_NOT_A_COUNT, ""),
    ("lane_board.lanes[].refusal_loop_seconds", S_DERIVED, M_NOT_A_COUNT, ""),
    ("lane_board.lanes[].failure_guard", S_WATCHER_LOG, M_NOT_A_COUNT, ""),
    ("lane_board.lanes[].failure_guard.*", S_WATCHER_LOG, M_NOT_A_COUNT, ""),
    # --------------------------------- one lane, the classified closed failures
    ("lane_board.lanes[].closed_failures", S_WATCHER_LOG, M_RAN_AND_REFUSED,
     "every DONE the watcher counted a FAILURE, so this list holds both - "
     "which is the point: each ROW below is classified"),
    ("lane_board.lanes[].closed_failures[].lane", S_WATCHER_LOG,
     M_NOT_A_COUNT, ""),
    ("lane_board.lanes[].closed_failures[].brief", S_WATCHER_LOG,
     M_NOT_A_COUNT, ""),
    ("lane_board.lanes[].closed_failures[].at", S_WATCHER_LOG,
     M_NOT_A_COUNT, ""),
    ("lane_board.lanes[].closed_failures[].date", S_WATCHER_LOG,
     M_NOT_A_COUNT, ""),
    ("lane_board.lanes[].closed_failures[].suffix", S_WATCHER_LOG,
     M_RAN_AND_REFUSED, ""),
    ("lane_board.lanes[].closed_failures[].line", S_WATCHER_LOG,
     M_NOT_A_COUNT, ""),
    ("lane_board.lanes[].closed_failures[].start_at", S_WATCHER_LOG,
     M_NOT_A_COUNT, ""),
    ("lane_board.lanes[].closed_failures[].outcome", S_OUT_TEXT,
     M_REFUSAL_SUBSTATES,
     "CONTENT AND NOTHING ELSE - not the exit code, not the byte count, not "
     "the lane. It separates RAN from REFUSED correctly and it CANNOT "
     "separate a refusal at dispatch from one that cut off a 59-minute run, "
     "because the two outputs are identical"),
    ("lane_board.lanes[].closed_failures[].outcome_label", S_SOURCE_PROSE,
     M_NOT_A_COUNT, ""),
    ("lane_board.lanes[].closed_failures[].outcome_implies", S_SOURCE_PROSE,
     M_NOT_A_COUNT,
     "THE ONE FIGURE ON THESE PAGES THAT WAS MEASURABLY FALSE. It asserted "
     "'so this task NEVER RAN' on all eight refusals; three of them ran for "
     "24.4, 59.1 and 59.3 minutes"),
    ("lane_board.lanes[].closed_failures[].refusal_line", S_OUT_TEXT,
     M_NOT_A_COUNT, ""),
    ("lane_board.lanes[].closed_failures[].status_code", S_OUT_TEXT,
     M_NOT_A_COUNT, ""),
    ("lane_board.lanes[].closed_failures[].refusal_line_but_also_output",
     S_OUT_TEXT, M_NOT_A_COUNT, ""),
    ("lane_board.lanes[].closed_failures[].never_ran_window_seconds",
     S_CONSTANT, M_NOT_A_COUNT, ""),
    ("lane_board.lanes[].closed_failures[].elapsed_seconds", S_DERIVED,
     M_NOT_A_COUNT,
     "DONE minus START, from the watcher's own two lines. The ONLY figure "
     "that distinguishes a refusal at dispatch from a run that was cut off"),
    ("lane_board.lanes[].closed_failures[].never_ran_supportable", S_DERIVED,
     M_NOT_A_COUNT,
     "True only where the refusal arrived inside the clock tolerance of this "
     "task's own START. False where it did not. None where either line is "
     "missing - and None is NOT True"),
    ("lane_board.lanes[].closed_failures[].out_name", S_WATCHER_LOG,
     M_NOT_A_COUNT, ""),
    ("lane_board.lanes[].closed_failures[].out_join", S_WATCHER_LOG,
     M_NOT_A_COUNT, ""),
    ("lane_board.lanes[].closed_failures[].out_join_why", S_SOURCE_PROSE,
     M_NOT_A_COUNT, ""),
    ("lane_board.lanes[].closed_failures[].out_ambiguous", S_WATCHER_LOG,
     M_NOT_A_COUNT, ""),
    ("lane_board.lanes[].closed_failures[].out_ambiguous[]", S_WATCHER_LOG,
     M_NOT_A_COUNT, ""),
    ("lane_board.lanes[].closed_failures[].out_state", S_OUT_BYTES,
     M_NOT_A_COUNT, ""),
    ("lane_board.lanes[].closed_failures[].out_bytes", S_OUT_BYTES,
     M_NOT_A_COUNT, ""),
    ("lane_board.lanes[].closed_failures[].out_truncated", S_OUT_BYTES,
     M_NOT_A_COUNT, ""),
    ("lane_board.lanes[].closed_failures[].reset.*", S_OUT_TEXT,
     M_NOT_A_COUNT, ""),
    ("lane_board.lanes[].closed_failures[].reset_from", S_MACHINE_CLOCK,
     M_NOT_A_COUNT, ""),
    ("lane_board.lanes[].closed_failures[].reset_to", S_MACHINE_CLOCK,
     M_NOT_A_COUNT, ""),
    ("lane_board.lanes[].closed_failures[].clock_check.*", S_DERIVED,
     M_NOT_A_COUNT,
     "the refusal's own request id carries a stamp on the provider's clock. "
     "Converted onto this estate's clock it lands within 1 second of the "
     "watcher's DONE line on all eight, which is what proves the refusal "
     "arrived at the END of each run"),
    ("lane_board.lanes[].closed_failures[].consumed.*", S_DONE_PATH,
     M_NOT_A_COUNT, ""),
    ("lane_board.lanes[].closed_failures[].still_missing", S_QUEUE_LISTING,
     M_NOT_A_COUNT,
     "asked of the QUEUE and of `RUNNING\\`, never of `DONE\\`: an "
     "unreadable directory never proves a brief missing"),
    ("lane_board.lanes[].closed_failures[].restored.*", S_QUEUE_LISTING,
     M_NOT_A_COUNT, ""),
    ("lane_board.lanes[].closed_failures_capped", S_CONSTANT,
     M_NOT_A_COUNT, ""),
    ("lane_board.lanes[].refused", S_OUT_TEXT, M_REFUSAL_SUBSTATES, ""),
    ("lane_board.lanes[].refused[].*", S_OUT_TEXT, M_REFUSAL_SUBSTATES, ""),
    ("lane_board.lanes[].refused_count", S_OUT_TEXT, M_REFUSAL_SUBSTATES, ""),
    ("lane_board.lanes[].unclassifiable_failures", S_OUT_BYTES,
     M_KEPT_APART,
     "kept apart from the refusal count ON PURPOSE: a failure whose output "
     "could not be read is NOT a refusal and is not an ordinary failure"),
    ("lane_board.lanes[].briefs_still_missing", S_QUEUE_LISTING,
     M_KEPT_APART, ""),
    ("lane_board.lanes[].briefs_missing_unknown", S_QUEUE_LISTING,
     M_KEPT_APART, ""),
    # ----------------------------------------------- the board's own aggregates
    ("lane_board.queued_total", S_QUEUE_LISTING, M_HANDCLOSED_INVISIBLE, ""),
    ("lane_board.queue_unreadable", S_QUEUE_LISTING, M_NOT_A_COUNT, ""),
    ("lane_board.owed_markers", S_LANE_FILE_TEXT, M_NOT_A_COUNT, ""),
    ("lane_board.owed_scope_shaky", S_LANE_FILE_TEXT, M_NOT_A_COUNT, ""),
    ("lane_board.refusals", S_OUT_TEXT, M_REFUSAL_SUBSTATES, ""),
    ("lane_board.refusals[].*", S_OUT_TEXT, M_REFUSAL_SUBSTATES, ""),
    ("lane_board.refused_total", S_OUT_TEXT, M_REFUSAL_SUBSTATES,
     "8 tonight, and the brief that sent this task said nine. The ninth, "
     "`glm-b/0170`, is a NOWORK whose `.out` holds 1,520 bytes of its own "
     "work report - a different defect, and this figure is right to exclude "
     "it"),
    ("lane_board.refused_by_lane", S_OUT_TEXT, M_REFUSAL_SUBSTATES, ""),
    ("lane_board.refused_by_lane[].*", S_OUT_TEXT, M_REFUSAL_SUBSTATES, ""),
    ("lane_board.refused_by_date", S_OUT_TEXT, M_REFUSAL_SUBSTATES, ""),
    ("lane_board.refused_by_date[].*", S_OUT_TEXT, M_REFUSAL_SUBSTATES, ""),
    ("lane_board.refused_first", S_WATCHER_LOG, M_REFUSAL_SUBSTATES,
     "the DONE time of the first refusal, which is the moment the brief was "
     "CONSUMED and not the moment the refusal began. `glm/0067b` started at "
     "00:42:31 and this figure reads 01:41:36"),
    ("lane_board.refused_last", S_WATCHER_LOG, M_REFUSAL_SUBSTATES, ""),
    ("lane_board.refused_never_ran", S_DERIVED, M_KEPT_APART,
     "refusals the board may still describe as never having run: the ones "
     "whose whole START..DONE interval fits inside the watcher's inter-task "
     "sleep. ZERO tonight, against eight refusals"),
    ("lane_board.refused_ran_unknown", S_DERIVED, M_KEPT_APART,
     "refusals whose session was alive long enough to act, with no record "
     "either way. EIGHT tonight. This is the figure the old glossary "
     "sentence denied the existence of"),
    ("lane_board.refused_elapsed_unknown", S_DERIVED, M_KEPT_APART, ""),
    ("lane_board.refused_unaccounted_seconds", S_DERIVED, M_KEPT_APART,
     "the total unrecorded window across every refusal. None rather than a "
     "partial sum if any row's interval is unmeasurable"),
    ("lane_board.refused_longest_seconds", S_DERIVED, M_KEPT_APART, ""),
    ("lane_board.never_ran_window_seconds", S_CONSTANT, M_NOT_A_COUNT, ""),
    ("lane_board.tally.*", S_DERIVED, M_KEPT_APART,
     "one key per VERDICT seen, counted off the verdicts rather than "
     "restated, so a new verdict cannot be absorbed into an existing bucket. "
     "The keys are dynamic, which is why this row is a subtree"),
    ("lane_board.briefs_still_missing", S_QUEUE_LISTING, M_KEPT_APART, ""),
    ("lane_board.briefs_missing_unknown", S_QUEUE_LISTING, M_KEPT_APART, ""),
    ("lane_board.unclassifiable_failures", S_OUT_BYTES, M_KEPT_APART, ""),
    ("lane_board.closed_failures_capped", S_CONSTANT, M_NOT_A_COUNT, ""),
    ("lane_board.reset_uncorroborated", S_DERIVED, M_NOT_A_COUNT, ""),
    ("lane_board.failure_guards", S_WATCHER_LOG, M_KEPT_APART, ""),
    ("lane_board.failure_guards[].*", S_WATCHER_LOG, M_KEPT_APART, ""),
    ("lane_board.floor", S_QUEUE_README, M_NOT_A_COUNT, ""),
    ("lane_board.floor_state", S_QUEUE_README, M_NOT_A_COUNT, ""),
    ("lane_board.floor_state_why", S_SOURCE_PROSE, M_NOT_A_COUNT, ""),
    ("lane_board.near_window_seconds", S_CONSTANT, M_NOT_A_COUNT,
     "ten minutes, from TASK-0150's brief. The clock panel labels its own "
     "alarm from this rather than holding a copy of the number, so a panel "
     "with no rows can still say what the window is"),
    ("lane_board.floor_path", S_QUEUE_README, M_NOT_A_COUNT, ""),
    ("lane_board.floor_path_shown", S_QUEUE_README, M_NOT_A_COUNT, ""),
    ("lane_board.floor_line", S_QUEUE_README, M_NOT_A_COUNT, ""),
    ("lane_board.local_offset_hours", S_MACHINE_CLOCK, M_NOT_A_COUNT, ""),
    ("lane_board.provider_offset_hours", S_CONSTANT, M_NOT_A_COUNT, ""),
    ("lane_board.unrecognised_verdicts", S_DERIVED, M_NOT_A_COUNT, ""),
    ("lane_board.unrecognised_verdicts[]", S_DERIVED, M_NOT_A_COUNT, ""),
    ("lane_board.outcome_glossary", S_SOURCE_PROSE, M_NOT_A_COUNT, ""),
    ("lane_board.outcome_glossary[].*", S_SOURCE_PROSE, M_NOT_A_COUNT, ""),
    ("lane_board.verdict_glossary", S_SOURCE_PROSE, M_NOT_A_COUNT, ""),
    ("lane_board.verdict_glossary[].*", S_SOURCE_PROSE, M_NOT_A_COUNT, ""),
    ("lane_board.suffix_glossary", S_SOURCE_PROSE, M_NOT_A_COUNT, ""),
    ("lane_board.suffix_glossary[].*", S_SOURCE_PROSE, M_NOT_A_COUNT, ""),
    ("lane_board.refused", S_SOURCE_PROSE, M_NOT_A_COUNT,
     "the board's list of sources it REFUSES to read. Prose, and checkable "
     "against this module's own table"),
    ("lane_board.refused[].*", S_SOURCE_PROSE, M_NOT_A_COUNT, ""),
    ("lane_board.cannot_see", S_SOURCE_PROSE, M_NOT_A_COUNT, ""),
    ("lane_board.cannot_see[].*", S_SOURCE_PROSE, M_NOT_A_COUNT, ""),
    # ------------------------------- the audit OF the folder, not FROM it
    #
    # The one place on these pages that lists a `DONE\` folder, and it is
    # covered by `ABOUT_THE_FOLDER` below so that it cannot be mistaken for
    # a figure about the work. It exists to say who wrote those filenames;
    # no task count, throughput, timestamp or success rate descends from it.
    ("lane_board.done_folders.*", S_DONE_LISTING, M_HANDCLOSED_INVISIBLE,
     "a LISTING, deliberately, and the only one on these pages. Every "
     "figure under it is a fact about the FOLDER - how many files it holds "
     "and which of them no watcher wrote - and never a fact about the work"),
    ("lane_board.done_folders.lanes[].log_state", S_WATCHER_LOG,
     M_NOT_A_COUNT, ""),
    ("lane_board.done_folders.lanes[].log_truncated", S_WATCHER_LOG,
     M_NOT_A_COUNT, ""),
    ("lane_board.done_folders.lanes[].done_lines", S_WATCHER_LOG,
     M_RAN_AND_REFUSED,
     "the count the folder is being checked AGAINST, from the log. The two "
     "disagreeing is the whole output of this block"),
    ("lane_board.done_folders.rules.*", S_SOURCE_PROSE, M_NOT_A_COUNT,
     "the six classification rules, printed whether or not each matched - a "
     "rule that matched nothing may be a clean estate or a broken pattern, "
     "and a dropped row cannot tell those apart"),
    # --------------------------------------------- the machine-wide lock
    #
    # THREE AUTHORITIES, AND MERGING ANY PAIR OF THEM IS THE DEFECT. The
    # lock file's bytes say who CLAIMS to hold it, the directory listing is
    # the only thing that can prove it FREE, and the process table is the
    # only thing that can prove the holder dead - which is ORPHAN, the state
    # this estate had no name for until 2026-10-16.
    ("lane_board.locks.at", S_MACHINE_CLOCK, M_NOT_A_COUNT, ""),
    ("lane_board.locks.table_read", S_PROCESS_TABLE, M_NOT_A_COUNT, ""),
    ("lane_board.locks.rows", S_SUITE_LOCK, M_NOT_A_COUNT, ""),
    ("lane_board.locks.rows[].name", S_CONSTANT, M_NOT_A_COUNT, ""),
    ("lane_board.locks.rows[].path", S_ENVIRONMENT, M_NOT_A_COUNT,
     "`suitelock.path()`, from `git rev-parse --git-common-dir` - the one "
     "path identical from the main checkout and from every worktree. Never "
     "rendered: the page shows the last three components"),
    ("lane_board.locks.rows[].path_shown", S_ENVIRONMENT, M_NOT_A_COUNT, ""),
    ("lane_board.locks.rows[].path_resolved", S_ENVIRONMENT, M_NOT_A_COUNT,
     "False means git could not answer, so this reader does not know WHICH "
     "lock to read. It guesses no path: a guessed one would be a different "
     "lock from the one every suite takes"),
    # THE STATE ITSELF. Registered against the LISTING rather than the file,
    # because the one state that would be most damaging to get wrong - FREE -
    # can only come from the listing, and a `.*` row over the subtree would
    # have charged it to the lock file's bytes.
    ("lane_board.locks.rows[].state", S_LOCK_DIR_LISTING, M_KEPT_APART,
     "five states, and the pairs a reader must be able to tell apart: FREE "
     "is proven by a successful listing, UNKNOWN is the absence of one, and "
     "ORPHAN is a lock file whose holder the PROCESS TABLE says is gone. "
     "Neither UNKNOWN nor ORPHAN may render as HELD and neither may render "
     "as FREE"),
    ("lane_board.locks.rows[].state_label", S_SOURCE_PROSE, M_NOT_A_COUNT,
     ""),
    ("lane_board.locks.rows[].state_why", S_SOURCE_PROSE, M_NOT_A_COUNT, ""),
    ("lane_board.locks.rows[].why", S_SOURCE_PROSE, M_NOT_A_COUNT,
     "the sentence naming WHICH read failed, so an UNKNOWN is actionable "
     "rather than merely honest"),
    ("lane_board.locks.rows[].remedy", S_SOURCE_PROSE, M_NOT_A_COUNT,
     "the exact command for a person. PROSE, with no route, button or form "
     "behind it: this panel reports, and clearing a machine-wide lock or "
     "killing its holder is an operator action"),
    ("lane_board.locks.rows[].pid", S_SUITE_LOCK, M_NOT_A_COUNT,
     "the number the HOLDER WROTE. On its own it establishes nothing - "
     "Windows reuses a pid - and it is never shown without the table's "
     "verdict beside it"),
    ("lane_board.locks.rows[].alive", S_PROCESS_TABLE, M_KEPT_APART,
     "True, False and None are three answers. None is the table unread, and "
     "it makes the lock HELD-UNKNOWN and never ORPHAN: a holder is not "
     "called dead on a failed read, which is how a running suite's lock was "
     "taken on 2026-10-02"),
    ("lane_board.locks.rows[].alive_why", S_SOURCE_PROSE, M_NOT_A_COUNT, ""),
    # PROGRESS, NOT LIVENESS, and the distinction is registered because the
    # estate's rule for a LANE's liveness IS this delta.
    ("lane_board.locks.rows[].cpu", S_CPU_DELTA, M_NOT_A_COUNT, ""),
    ("lane_board.locks.rows[].cpu.pid", S_SUITE_LOCK, M_NOT_A_COUNT, ""),
    ("lane_board.locks.rows[].cpu.seconds", S_PROCESS_TABLE, M_NOT_A_COUNT,
     "accumulated kernel+user CPU for the holder AND EVERYTHING UNDER IT. "
     "The holder alone is not the figure: measured 2026-10-16, the pid a "
     "lock records is the pid that called `acquire`, which for a suite is a "
     "wrapper that then waits - 0.047s of its own against 92.6s in its "
     "child. None where every handle in the subtree was refused, which is "
     "counted as alive and unmeasured and never as zero"),
    ("lane_board.locks.rows[].cpu.pids", S_PROCESS_TABLE, M_NOT_A_COUNT, ""),
    ("lane_board.locks.rows[].cpu.pids[]", S_PROCESS_TABLE, M_NOT_A_COUNT,
     ""),
    ("lane_board.locks.rows[].cpu.count", S_PROCESS_TABLE, M_NOT_A_COUNT,
     "an UPPER BOUND on the holder's subtree rather than a proof of "
     "lineage: Windows reuses a pid, and a process whose real parent has "
     "exited keeps a parent pid that may now name something else"),
    ("lane_board.locks.rows[].cpu.unmeasured", S_PROCESS_TABLE,
     M_NOT_A_COUNT, ""),
    ("lane_board.locks.rows[].cpu.unmeasured[]", S_PROCESS_TABLE,
     M_NOT_A_COUNT, ""),
    ("lane_board.locks.rows[].cpu.delta_seconds", S_CPU_DELTA, M_KEPT_APART,
     "PROGRESS and not liveness. A suite blocked on a socket accrues no "
     "measurable CPU while being perfectly alive, so a zero here is a "
     "reason to look and is never the reason this lock reads ORPHAN"),
    ("lane_board.locks.rows[].cpu.wall_seconds", S_MACHINE_CLOCK,
     M_NOT_A_COUNT, ""),
    ("lane_board.locks.rows[].cpu.progressing", S_CPU_DELTA, M_NOT_A_COUNT,
     "None is UNKNOWN - a first look has no delta, and two looks in the "
     "same second have no window"),
    ("lane_board.locks.rows[].cpu.why", S_SOURCE_PROSE, M_NOT_A_COUNT, ""),
    ("lane_board.locks.rows[].branch", S_SUITE_LOCK, M_NOT_A_COUNT,
     "what the holder called itself. A detached checkout is recorded as "
     "`detached <sha>`, because this field read the literal string `HEAD` "
     "until 2026-10-02 and three agents then went looking for the holder by "
     "hand"),
    ("lane_board.locks.rows[].worktree_shown", S_SUITE_LOCK, M_NOT_A_COUNT,
     "the holder's working directory, LAST COMPONENT ONLY - the full path "
     "is somebody's home directory in a screenshot"),
    ("lane_board.locks.rows[].started_at", S_SUITE_LOCK, M_KEPT_APART,
     "when the holder TOOK the lock, stamped at the moment the write "
     "succeeded. Kept apart from `queued_at`, which is when it was "
     "launched: merging them overstated one hold by 39 minutes, and the "
     "obvious response to that figure is to kill a healthy run"),
    ("lane_board.locks.rows[].queued_at", S_SUITE_LOCK, M_KEPT_APART, ""),
    ("lane_board.locks.rows[].held_seconds", S_DERIVED, M_NOT_A_COUNT,
     "`started_at` against this machine's clock. None where the stamp is "
     "absent or unparseable, and a NEGATIVE value is returned as-is rather "
     "than clamped - a lock stamped in the future is a real condition"),
    ("lane_board.locks.rows[].queue_wait_seconds", S_DERIVED, M_NOT_A_COUNT,
     ""),
    ("lane_board.locks.rows[].recorded_path_shown", S_SUITE_LOCK,
     M_NOT_A_COUNT, ""),
    ("lane_board.locks.rows[].path_agrees", S_DERIVED, M_NOT_A_COUNT,
     "the path the lock was PUBLISHED to against the path resolved now. "
     "False means the lock has become per-worktree, which is the exact "
     "defect `suitelock` exists to prevent and the reason six concurrent "
     "suites serialised nothing on 2026-10-02"),
    ("lane_board.locks.rows[].waiters.*", S_LOCK_QUEUE, M_NOT_A_COUNT, ""),
    ("lane_board.locks.rows[].waiters.tickets[].alive", S_PROCESS_TABLE,
     M_NOT_A_COUNT, ""),
    ("lane_board.locks.held", S_PROCESS_TABLE, M_KEPT_APART, ""),
    ("lane_board.locks.free", S_LOCK_DIR_LISTING, M_KEPT_APART, ""),
    ("lane_board.locks.orphan", S_PROCESS_TABLE, M_KEPT_APART, ""),
    ("lane_board.locks.held_unknown", S_PROCESS_TABLE, M_KEPT_APART, ""),
    ("lane_board.locks.unknown", S_LOCK_DIR_LISTING, M_KEPT_APART,
     "the locks whose authority could not be consulted at all. Counted "
     "separately from `held_unknown`, which HAS a usable holder it could "
     "not check - two different things to do about them"),
    ("lane_board.locks.glossary", S_SOURCE_PROSE, M_NOT_A_COUNT, ""),
    ("lane_board.locks.glossary[].*", S_SOURCE_PROSE, M_NOT_A_COUNT, ""),
    # ----------------------------------------- the provenance table itself
    ("lane_board.provenance.*", S_SOURCE_PROSE, M_NOT_A_COUNT,
     "this table. Its own rows are prose in this module's source, and its "
     "coverage verdict is arithmetic over the live paths"),
    # -------------------------------------------------- the criteria page
    ("exit_criteria.*", S_OPS_DOCUMENTS, M_NOT_A_COUNT,
     "every verdict, tally, corroboration note and CONTESTED marker on that "
     "page descends from the verdict tables inside the named authority "
     "documents. It reads no watcher log, no `.out` file, no `DONE\\` folder "
     "and no process - so not one figure on it can be moved by a false DONE "
     "entry, and its exposure is a STALE or CONTESTED document instead"),
    # ------------------------------------------------- the breach ledger page
    #
    # EVERY HISTORICAL FIGURE ON THIS PAGE DESCENDS FROM OUR OWN LEDGER and
    # not from the estate directly, which is a different exposure from the
    # board's: the rows are samples the page itself took, so a gap is a gap
    # in the WATCHING. The present-tense columns are the exception and are
    # registered separately, because a reader comparing "now" with "the last
    # 24 hours" is comparing two sources.
    ("floor_ledger.at", S_MACHINE_CLOCK, M_NOT_A_COUNT, ""),
    ("floor_ledger.root_name", S_ENVIRONMENT, M_NOT_A_COUNT, ""),
    ("floor_ledger.board_state", S_ENVIRONMENT, M_NOT_A_COUNT, ""),
    ("floor_ledger.ledger_name", S_CONSTANT, M_NOT_A_COUNT, ""),
    ("floor_ledger.ledger_state", S_OWN_LEDGER, M_NOT_A_COUNT, ""),
    ("floor_ledger.ledger_rows", S_OWN_LEDGER, M_NOT_A_COUNT, ""),
    ("floor_ledger.ledger_lines", S_OWN_LEDGER, M_NOT_A_COUNT, ""),
    ("floor_ledger.damaged", S_OWN_LEDGER, M_NOT_A_COUNT, ""),
    ("floor_ledger.damaged[].*", S_OWN_LEDGER, M_NOT_A_COUNT, ""),
    ("floor_ledger.damaged_rows", S_OWN_LEDGER, M_NOT_A_COUNT,
     "printed whether it is zero or not. A row that could not be read is "
     "not skipped: it makes the stretch it sits in UNKNOWN"),
    ("floor_ledger.append_state", S_OWN_LEDGER, M_NOT_A_COUNT, ""),
    ("floor_ledger.append_why", S_SOURCE_PROSE, M_NOT_A_COUNT, ""),
    ("floor_ledger.append_written", S_OWN_LEDGER, M_NOT_A_COUNT, ""),
    ("floor_ledger.floor", S_QUEUE_README, M_NOT_A_COUNT, ""),
    ("floor_ledger.floor_state", S_QUEUE_README, M_NOT_A_COUNT, ""),
    ("floor_ledger.floor_state_why", S_SOURCE_PROSE, M_NOT_A_COUNT, ""),
    ("floor_ledger.floor_path_shown", S_QUEUE_README, M_NOT_A_COUNT, ""),
    ("floor_ledger.floor_line", S_QUEUE_README, M_NOT_A_COUNT, ""),
    ("floor_ledger.window_seconds", S_CONSTANT, M_NOT_A_COUNT, ""),
    ("floor_ledger.max_gap_seconds", S_CONSTANT, M_NOT_A_COUNT, ""),
    ("floor_ledger.totals_available", S_OWN_LEDGER, M_NOT_A_COUNT, ""),
    ("floor_ledger.no_totals_why", S_SOURCE_PROSE, M_NOT_A_COUNT, ""),
    ("floor_ledger.lane_count", S_DERIVED, M_NOT_A_COUNT, ""),
    ("floor_ledger.lanes", S_OWN_LEDGER, M_NOT_A_COUNT, ""),
    ("floor_ledger.lanes[].*", S_OWN_LEDGER, M_NOT_A_COUNT, ""),
    # The three present-tense columns, which come from the BOARD and
    # therefore inherit the board's provenance - named apart so a reader
    # cannot take them for ledger history.
    ("floor_ledger.lanes[].current_depth", S_QUEUE_LISTING,
     M_HANDCLOSED_INVISIBLE, "NOW, from the board, and not part of the "
     "history. Labelled as such wherever it is shown"),
    ("floor_ledger.lanes[].current_state", S_DERIVED, M_NOT_A_COUNT,
     "NOW, from the board: the log crossed with the process table"),
    ("floor_ledger.lanes[].current_below_floor", S_DERIVED, M_NOT_A_COUNT,
     "NOW, from the board"),
    ("floor_ledger.estate", S_OWN_LEDGER, M_NOT_A_COUNT, ""),
    ("floor_ledger.estate.*", S_OWN_LEDGER, M_NOT_A_COUNT, ""),
    ("floor_ledger.bucket_glossary", S_SOURCE_PROSE, M_NOT_A_COUNT, ""),
    ("floor_ledger.bucket_glossary[].*", S_SOURCE_PROSE, M_NOT_A_COUNT, ""),
    ("floor_ledger.hole_glossary", S_SOURCE_PROSE, M_NOT_A_COUNT, ""),
    ("floor_ledger.hole_glossary[].*", S_SOURCE_PROSE, M_NOT_A_COUNT, ""),
    ("floor_ledger.cannot_see", S_SOURCE_PROSE, M_NOT_A_COUNT, ""),
    ("floor_ledger.cannot_see[].*", S_SOURCE_PROSE, M_NOT_A_COUNT, ""),
    ("floor_ledger.provenance.*", S_SOURCE_PROSE, M_NOT_A_COUNT, ""),
)


#: Patterns whose figures are facts about a `DONE\` FOLDER rather than about
#: the work done in the estate.
#:
#: WHY THIS DISTINCTION IS LOAD-BEARING AND NOT A HEDGE. The result of this
#: task is "no figure on these pages counts work from a `DONE\` filename", and
#: the moment an audit block was added that lists those folders on purpose,
#: the unqualified claim became false - the source's figure count went from 0
#: to 1 and the sentence had nothing left to stand on. Rather than quietly
#: exempting the block or dropping the claim, the claim is narrowed to the
#: thing that was ever true and is now CHECKABLE: `work_figures` below counts
#: figures reading a source and NOT in this set, so
#: `work_figures[S_DONE_LISTING] == 0` is one assertion a control can make and
#: a future block that reads a listing for a throughput will break it.
ABOUT_THE_FOLDER = ("lane_board.done_folders.*",)


def _to_regex(pattern):
    """A figure pattern as an anchored regex. `[]` is a list index, `.*` a
    subtree, and every other character is literal.

    `re.escape` first, so a `.` in a key name cannot match any character -
    which would make `lane_board.floor` cover `lane_boardXfloor` and, far
    worse, make a trailing `.*` match a sibling key.
    """
    out = []
    i = 0
    while i < len(pattern):
        if pattern.startswith("[]", i):
            out.append(r"\[\]")
            i += 2
        elif pattern.startswith(".*", i) and i + 2 == len(pattern):
            # A subtree: this node and everything under it.
            out.append(r"(?:\..*)?")
            i += 2
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.compile("^" + "".join(out) + "$")


#: Compiled once. `FIGURES` is a module constant and the patterns never change
#: at runtime, so rebuilding them per call would be the only cost here.
_COMPILED = tuple((pattern, _to_regex(pattern), source, merges, note)
                  for pattern, source, merges, note in FIGURES)


def figure_for(path):
    """The registry row covering `path`, or None. LONGEST PATTERN WINS.

    A specific leaf and the `.*` subtree that contains it may both match, and
    the leaf's own row is the one with something to say. Ordering by pattern
    length rather than by position in `FIGURES` means the registry can be
    maintained in reading order without the ordering becoming load-bearing -
    a subtree row accidentally written above its leaves would otherwise
    swallow them silently.
    """
    best = None
    for pattern, regex, source, merges, note in _COMPILED:
        if not regex.match(path):
            continue
        if best is None or len(pattern) > len(best[0]):
            best = (pattern, source, merges, note)
    if best is None:
        return None
    pattern, source, merges, note = best
    return {"pattern": pattern, "source": source, "merges": merges,
            "note": note}


def coverage(paths):
    """Which live figure paths have a provenance row, and which do not.

    `uncovered` IS THE FINDING AND IS NEVER EMPTY BY DEFAULT: a figure added
    to one of these pages with no row here arrives in it, and the page is
    required to render that figure UNKNOWN and name it. The alternative -
    defaulting an unmatched path to "probably the watcher log" - is this
    repository's own signature defect, a plausible answer standing in for a
    missing one.
    """
    covered, uncovered = [], []
    for path in sorted(set(paths)):
        found = figure_for(path)
        if found is None:
            uncovered.append(path)
        else:
            covered.append(dict(found, path=path))
    return {"covered": covered, "uncovered": uncovered,
            "paths": len(set(paths))}


def sources_used(paths):
    """`{source_key: [patterns that matched at least one live path]}`.

    EVERY SOURCE IS A KEY, including the ones that matched nothing. A source
    with an empty list is the measurement "no figure on these pages reads
    this", and that is the whole answer to the DONE-folder question - so it
    has to be a row that says zero, never a row that is absent.
    """
    used = {key: set() for key in SOURCES}
    for row in coverage(paths)["covered"]:
        used[row["source"]].add(row["pattern"])
    return {key: sorted(value) for key, value in used.items()}


def work_figures(paths):
    """`{source_key: [patterns]}` for figures ABOUT THE WORK.

    `sources_used` minus `ABOUT_THE_FOLDER`. Every source is still a key and
    an empty list is still a measured zero - the exclusion changes which
    patterns are counted and never whether a source gets a row.
    """
    excluded = {p for p in ABOUT_THE_FOLDER}
    return {key: [p for p in patterns if p not in excluded]
            for key, patterns in sources_used(paths).items()}


def table(paths):
    """The provenance table, one row per live figure path, ready to render."""
    found = coverage(paths)
    rows = []
    for row in found["covered"]:
        source = SOURCES[row["source"]]
        auth_label, auth_why = AUTHORITY_TEXT[source["authority"]]
        merge_label, merge_why = MERGE_TEXT[row["merges"]]
        rows.append({
            "path": row["path"],
            "pattern": row["pattern"],
            "source": row["source"],
            "source_label": source["label"],
            "authority": source["authority"],
            "authority_label": auth_label,
            "authority_why": auth_why,
            "authority_quote": source["quote"],
            "can_be_false": source["can_be_false"],
            "can_be_false_why": source["why"],
            "merges": row["merges"],
            "merges_label": merge_label,
            "merges_why": merge_why,
            "note": row["note"],
            "state": "covered",
        })
    for path in found["uncovered"]:
        # UNKNOWN, and every field that would normally carry a reassurance is
        # None rather than a default. A reader must not be able to mistake
        # this row for a sourced one.
        rows.append({
            "path": path, "pattern": None, "source": None,
            "source_label": None, "authority": None, "authority_label": None,
            "authority_why": None, "authority_quote": None,
            "can_be_false": None,
            "can_be_false_why": "PROVENANCE UNKNOWN. No row in "
                                "src/laneprovenance.py covers this path, so "
                                "nothing here can say what file it descends "
                                "from or whether that file can lie. It "
                                "renders UNKNOWN",
            "merges": None, "merges_label": None, "merges_why": None,
            "note": "", "state": "unknown",
        })
    rows.sort(key=lambda r: (r["state"] != "unknown", r["path"]))
    work = work_figures(paths)
    return {
        "rows": rows,
        "paths": found["paths"],
        "covered": len(found["covered"]),
        "uncovered": len(found["uncovered"]),
        # A source that matched nothing, reported as a zero. Both halves
        # matter: the DONE listing matching zero is the result, and a source
        # matching zero because its pattern broke is a bug, and the only way
        # to tell them apart is to look at the row.
        "sources": [
            {"source": key,
             "label": SOURCES[key]["label"],
             "authority": SOURCES[key]["authority"],
             "authority_label": AUTHORITY_TEXT[SOURCES[key]["authority"]][0],
             "can_be_false": SOURCES[key]["can_be_false"],
             "why": SOURCES[key]["why"],
             "quote": SOURCES[key]["quote"],
             "patterns": patterns,
             "figures": len(patterns),
             # Figures ABOUT THE WORK, which is the number the claim rests
             # on. Equal to `figures` everywhere except the one block that
             # audits a `DONE\` folder on purpose.
             "work_figures": len(work.get(key, []))}
            for key, patterns in sorted(sources_used(paths).items())],
    }


def paths_of(blob, prefix):
    """Every distinct figure path in an API payload, list indices as `[]`.

    The same walk the registry is checked against, so the check cannot drift
    from the thing being checked by using a second traversal.
    """
    found = set()

    def walk(node, path):
        if isinstance(node, dict):
            for key in node:
                walk(node[key], "%s.%s" % (path, key))
        elif isinstance(node, (list, tuple)):
            found.add(path)
            for item in node:
                walk(item, path + "[]")
        else:
            found.add(path)

    walk(blob, prefix)
    return found


# ----------------------------------- who wrote the names in the DONE folders
#
# The reverse question, and the one a count of the folder cannot answer. Every
# rule below is reported WITH ITS COUNT EVEN WHEN THAT COUNT IS ZERO: a rule
# matching nothing may be a clean estate or a broken pattern, and a dropped
# row cannot tell those apart.

R_LOGGED = "logged"
R_HAND_DECLARED = "hand_declared"
R_HAND_UNDECLARED = "hand_undeclared"
R_HAND_ANNOTATED = "hand_annotated"
R_SELF_WRITTEN = "self_written"
R_UNSHAPED = "unshaped"
R_LOGGED_NO_FILE = "logged_no_file"

#: The order the rules are APPLIED in, and also the order they are reported
#: in. One rule per file: the first that matches wins, so the counts sum to
#: the number of files and a reader can add them up.
RULE_ORDER = (R_LOGGED, R_HAND_DECLARED, R_SELF_WRITTEN, R_HAND_ANNOTATED,
              R_HAND_UNDECLARED, R_UNSHAPED, R_LOGGED_NO_FILE)

RULE_TEXT = {
    R_LOGGED: (
        "LOGGED",
        "the filename is exactly `<stamp>-<suffix>-<brief>` for a `DONE` line "
        "in this lane's log, with the stamp taken from that line's own MOVED "
        "entry where there is one and from its paired START where there is "
        "not. This entry traces to the authority"),
    R_HAND_DECLARED: (
        "HAND-CLOSED, AND IT SAYS SO",
        "the filename carries `HANDCLOSED` and no `DONE` line in this lane's "
        "log names the brief. A person closed it and wrote that into the "
        "name, which is the best case: the name is the only statement about "
        "the task that exists and it does not pretend to be a watcher's"),
    R_HAND_UNDECLARED: (
        "HAND-CLOSED, AND IT DOES NOT SAY SO",
        "no `DONE` line names this brief, and the filename carries a "
        "watcher-shaped stamp and suffix with nothing in it saying a person "
        "wrote it. THE DANGEROUS SHAPE: it reads as a watcher entry to any "
        "human and to any parser, and the only thing that refutes it is the "
        "absence of a log line. `TIMEOUT-but-complete` is the measured "
        "instance - a verdict about the WORK, which no watcher ever writes"),
    R_HAND_ANNOTATED: (
        "HAND-ANNOTATED",
        "a `DONE` line names this brief and the filename is the watcher's "
        "with words inserted into it by a person. The event is real and the "
        "NAME is no longer the watcher's, so anything parsing the name reads "
        "a suffix the watcher never wrote"),
    R_SELF_WRITTEN: (
        "WRITTEN BY THE TASK ITSELF",
        "a `DONE` line names this brief and this file's stamp is not the one "
        "that line implies. Measured cause, from the lane's own entry: the "
        "watcher's removal of the brief from `RUNNING\\` was refused by an "
        "open file handle, so the SESSION wrote its own copy into `DONE\\` "
        "and the watcher later wrote another. One task, two entries"),
    R_UNSHAPED: (
        "NO WATCHER SHAPE AT ALL",
        "the filename carries no `<8 digits>-<6 digits>-<suffix>-` prefix, so "
        "no watcher wrote it under any circumstances - a four-digit time or "
        "no stamp at all. Author and moment are both UNKNOWN and the file's "
        "own mtime cannot date the move, because `Move-Item` preserves it"),
    R_LOGGED_NO_FILE: (
        "LOGGED WITH NO FILE",
        "this lane's log holds a `DONE` line whose implied entry is not in "
        "`DONE\\`. THE DIRECTION A COUNT OF THE FOLDER CAN NEVER SEE: work "
        "the authority recorded and the folder does not hold"),
}

#: `<8>-<6>-<suffix>-<brief>.md`. The suffix is alphanumeric only, so a
#: hand-inserted `-but-complete` falls outside it and is detected rather than
#: absorbed into the suffix.
_SHAPED = re.compile(r"^(\d{8}-\d{6})-([A-Za-z0-9]+)-(.+\.md)$")

#: What a person writes into a name to say they closed it by hand. Checked
#: case-insensitively and ANYWHERE in the name, because the estate's twelve
#: put it after a four-digit stamp and one of those also carries `DUPLIKAT-OD`
#: in front of the brief - a convention, not a format.
_DECLARED = re.compile(r"(?i)HANDCLOSED")


def _implied_names(events):
    """`{filename: done_event}` for every DONE line, by the watcher's own
    construction, plus `{brief: [stamps]}` for the briefs it names.

    The stamp comes from the MOVED line where there is one - an authority
    rather than an inference - and otherwise from the START paired with this
    DONE, which is the same fallback `join_out` uses and for the same reason.
    """
    implied, by_brief = {}, {}
    for index, event in enumerate(events):
        if event["kind"] != "done":
            continue
        stamp = lanes._moved_stamp(events, index, event["task"])
        if not stamp:
            for earlier in reversed(events[:index]):
                if earlier["kind"] in ("start", "done"):
                    if (earlier["kind"] == "start"
                            and earlier["task"] == event["task"]
                            and earlier["when"] is not None):
                        stamp = earlier["when"].strftime("%Y%m%d-%H%M%S")
                    break
        by_brief.setdefault(event["task"], []).append(stamp)
        if stamp:
            implied["%s-%s-%s" % (stamp, event["suffix"], event["task"])] = event
    return implied, by_brief


def reconcile_lane(root, lane):
    """Every `DONE\\` file in one lane, against that lane's watcher log.

    Returns a verdict per file and the reverse direction too. Reads only;
    nothing in `DONE\\` is created, renamed, moved or removed.
    """
    log_path = os.path.join(root, "logs", "watcher-%s.log" % lane)
    log_state, lines, truncated = lanes._read_tail(log_path)
    events = (lanes.watcher_events(lines, lane)
              if log_state == lanes.PRESENT else [])
    implied, by_brief = _implied_names(events)

    done_dir = os.path.join(root, "queue", lane, "DONE")
    dir_state, names = lanes._list_md(done_dir)

    files, seen = [], set()
    for name in names:
        # 1. The watcher's own name for a DONE line it wrote. The only rule
        #    that makes an entry traceable, and it is an equality - no
        #    prefix match, no tolerance.
        if name in implied:
            files.append({"name": name, "rule": R_LOGGED,
                          "line": implied[name]["line"], "logged_stamps": None})
            seen.add(name)
            continue
        shaped = _SHAPED.match(name)
        brief = shaped.group(3) if shaped else None
        logged_stamps = [s for s in by_brief.get(brief, []) if s] if brief \
            else []
        # 2. A declared hand close, BEFORE the shape test, because the twelve
        #    in this estate carry a four-digit time and would otherwise be
        #    binned as merely unparseable - which would lose the one piece of
        #    information that makes them the harmless kind. A declaration on
        #    a brief the log DOES name is not accepted: that is a logged
        #    task wearing a hand label, and rule 3 or 4 has to see it first,
        #    which is what control C4 pins.
        if _DECLARED.search(name) and brief not in by_brief:
            files.append({"name": name, "rule": R_HAND_DECLARED, "line": None,
                          "logged_stamps": None})
            continue
        if not shaped:
            files.append({"name": name, "rule": R_UNSHAPED, "line": None,
                          "logged_stamps": None})
            continue
        # 3. The log names this brief and this file is not the entry that
        #    line implies. One task, two entries.
        if brief in by_brief:
            files.append({"name": name, "rule": R_SELF_WRITTEN, "line": None,
                          "logged_stamps": logged_stamps})
            continue
        # 4. The stamp and suffix are the watcher's shape and no DONE line
        #    names this brief. Either a person wrote the whole name, or a
        #    person EDITED a watcher name so the brief no longer parses out
        #    of it. Those are told apart by asking whether this file's stamp
        #    is one the log does name - under a different brief, because the
        #    insertion moved the boundary.
        stamp = shaped.group(1)
        annotated = [done for name2, done in implied.items()
                     if name2.startswith(stamp + "-")]
        if annotated:
            files.append({"name": name, "rule": R_HAND_ANNOTATED,
                          "line": annotated[0]["line"], "logged_stamps": None})
            continue
        # 5. Watcher-shaped, no log line, and nothing in the name admitting
        #    it. The shape a reader cannot tell from a real entry.
        files.append({"name": name, "rule": R_HAND_UNDECLARED, "line": None,
                      "logged_stamps": None})

    missing = [{"name": name, "rule": R_LOGGED_NO_FILE,
                "line": done["line"], "logged_stamps": None}
               for name, done in sorted(implied.items()) if name not in seen]

    counts = {rule: 0 for rule in RULE_ORDER}
    for row in files + missing:
        counts[row["rule"]] += 1
    return {
        "lane": lane,
        "log_state": log_state,
        "log_truncated": truncated,
        "done_state": dir_state,
        # None, NOT 0, when the folder could not be listed. An unreadable
        # directory holds no information about how many files are in it, and
        # 0 would read as a clean lane.
        "files": None if dir_state != lanes.PRESENT else len(names),
        "done_lines": len([e for e in events if e["kind"] == "done"]),
        "rows": files + missing,
        "counts": counts,
    }


def reconcile(root=None):
    """Every lane's `DONE\\` folder against its log. Every rule, every count.

    `untraceable` is the number a reader needs and the one the folder cannot
    produce: files whose names no watcher wrote. Measured 2026-10-16 across
    seven lanes, it is 21 of 152.
    """
    root = root or lanes.ops_root()
    if root is None:
        return {"state": lanes.UNCONFIGURED, "root": None, "lanes": [],
                "counts": {rule: None for rule in RULE_ORDER},
                "files": None, "untraceable": None, "rules": _rule_rows()}
    if not os.path.isdir(root):
        return {"state": lanes.ABSENT, "root": root, "lanes": [],
                "counts": {rule: None for rule in RULE_ORDER},
                "files": None, "untraceable": None, "rules": _rule_rows()}
    rows = [reconcile_lane(root, lane) for lane, _where in
            lanes.lane_names(root)]
    counts = {rule: sum(row["counts"][rule] for row in rows)
              for rule in RULE_ORDER}
    readable = [row for row in rows if row["done_state"] == lanes.PRESENT]
    return {
        "state": lanes.PRESENT,
        "root": root,
        "lanes": rows,
        "counts": counts,
        # None when ANY lane's folder could not be listed: a total over a
        # subset is not the total and must not be printed as one.
        "files": (sum(row["files"] for row in readable)
                  if len(readable) == len(rows) else None),
        # Files whose names no watcher wrote, by whichever rule caught them.
        # Derived from RULE_ORDER minus the two traceable verdicts rather
        # than from a hand-written list of four, so a seventh rule added
        # above is in this total on the day it lands - a count that has to be
        # remembered separately is a count that drifts.
        "untraceable": sum(counts[rule] for rule in RULE_ORDER
                           if rule not in (R_LOGGED, R_LOGGED_NO_FILE)),
        "unreadable_lanes": [row["lane"] for row in rows
                             if row["done_state"] != lanes.PRESENT],
        "rules": _rule_rows(),
    }


def _rule_rows():
    """The rules themselves, in order, so a page can print what each one is
    even when it matched nothing."""
    return [{"rule": rule, "label": RULE_TEXT[rule][0],
             "why": RULE_TEXT[rule][1]} for rule in RULE_ORDER]
