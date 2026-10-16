"""Whether a dispatched brief's work had already landed before the dispatch.

WHAT THIS MODULE IS FOR. The lane watcher dispatches the lowest-numbered file
in `queue/<lane>/` and has no way to ask whether that work is already done.
A lane session that runs ahead of its own queue - which the standing rules
require it to do, "start the next-numbered task without being told" - has no
way to tell the watcher. So a finished brief gets dispatched again, a fresh
session spends a full run re-deriving an artifact that already exists, and
nothing in the estate records that it happened. Measured 2026-10-16: at
least six times in six hours.

This module makes it visible and prices it. It does not fix it. The fix the
measuring lane named - have the watcher skip a brief whose TASK id already
appears in `LANE-<lane>.md` - is a one-line change to a PowerShell script
and is not this module's business.

THE AUTHORITY, AND IT IS PROSE. For each `START` line in
`logs/watcher-<lane>.log`, the question is whether an entry for that TASK id
already existed in `LANE-<lane>.md` at that moment. The lane file is
append-only prose written by a different model every run, not a ledger: its
entry headings carry a date sometimes, a time range sometimes, a tilde
sometimes, a `Z` suffix sometimes, and nothing at all often. So the dating
is a LADDER of four rungs, each naming the exact field it read, plus one
rung that is not a date at all - the lane saying in its own entry that it
found the work already done - and a START
nothing on the ladder reaches is UNKNOWN rather than clean.

WHY UNKNOWN IS KEPT APART FROM ZERO. `src.lanes.OUTCOME_TEXT[refused]` once
asserted "this task NEVER RAN" about eight tasks that between them ran 158.5
unrecorded minutes, because an unknown was rendered as the nearest available
name. The states here are five and they do not collapse: REWORK, FRESH,
NO_ENTRY, UNDATED and UNREADABLE. Only the first is a confirmed
re-dispatch; only the last two are absences of an answer; and a lane whose
log cannot be read is UNREADABLE in every cell rather than zero in all of
them.

WHAT THIS CANNOT SEE, SAID BEFORE THE NUMBERS. Three blind spots, each
measured rather than asserted, in `blind_spots()`:

1. A run that committed its work and wrote no lane entry is invisible to the
   lane-file authority and reads as NO_ENTRY. `glm/0060` did exactly that.
   `commit_only()` prices this cohort against git instead, separately,
   because it is a different authority and must not be folded into the
   headline.
2. TASK id equality is not task equality. `pilotcaps` 0233 and 0235 were
   rewritten while keeping their filenames and numbers, deliberately, so the
   dispatcher's sort order would hold. An entry for the old 0233 is not an
   entry for the new one. `REWRITTEN` marks every START whose brief file is
   newer than the entry that would otherwise clear it.
3. The watcher appends each task's whole stdout into the same log, so a task
   that printed a line of the watcher's own shape is indistinguishable from a
   watcher record. `src.lanes.watcher_events` anchors on the full prefix AND
   the lane tag, which removes all of it in this corpus and is not a proof.

READ-ONLY BY CONSTRUCTION. Nothing here opens a file for writing, creates a
directory, or runs a command other than `git` reads. The git seam is
injectable so a test needs no repository, and the default implementation
runs `cat-file --batch-check` and `log --no-walk`, both of which are reads.
"""
import datetime
import os
import re
import subprocess

from src import lanes


# --------------------------------------------------------------- the verdicts
#
# FIVE, and the reason they are five is that they have five different
# repairs. Rolling NO_ENTRY and UNDATED together would make "the lane file
# says nothing about this id" and "the lane file says something undatable"
# render identically, and only the second one is worth a person's attention.

#: An entry for this TASK id is dated strictly before the START. Confirmed.
REWORK = "rework"

#: Every entry for this id is positively dated at or after the START, so the
#: dispatch is the run that produced them. NOT a re-dispatch, and proven.
FRESH = "fresh"

#: The lane file holds no entry naming this id. NOT a re-dispatch - and not
#: UNKNOWN either, because the authority the brief names is readable and
#: answers. Its limit is blind spot 1 above, which `commit_only()` prices.
NO_ENTRY = "no_entry"

#: An entry exists and nothing on the ladder dates it. UNKNOWN. This never
#: becomes FRESH: an entry that cannot be dated is not an entry that closed
#: after the dispatch.
UNDATED = "undated"

#: The lane's log or lane file could not be read. UNKNOWN for every cell of
#: that lane, which is strictly less than an empty answer.
UNREADABLE = "unreadable"

VERDICT_ORDER = (REWORK, FRESH, NO_ENTRY, UNDATED, UNREADABLE)

VERDICT_TEXT = {
    REWORK: ("re-dispatched",
             "an entry for this TASK id is dated before the START line, so "
             "the work had already landed when the watcher dispatched it"),
    FRESH: ("first run",
            "every entry for this TASK id is positively dated at or after "
            "the START, so this dispatch is the run that produced them"),
    NO_ENTRY: ("no entry",
               "the lane file names this TASK id in no entry heading. Not a "
               "re-dispatch by this authority - but a run that committed "
               "and wrote no entry looks exactly like this"),
    UNDATED: ("UNKNOWN - entry undated",
              "an entry for this TASK id exists and no rung of the ladder "
              "dates it. Not cleared and not counted"),
    UNREADABLE: ("UNKNOWN - no authority",
                 "this lane's watcher log or lane file could not be read, "
                 "so every cell is the absence of an answer rather than a "
                 "zero"),
}

#: The verdicts that mean "this dispatch did not repeat finished work". Kept
#: as a tuple rather than `not REWORK`, so a verdict added later has to be
#: classified deliberately instead of falling into the clean bucket.
NOT_REWORK = (FRESH, NO_ENTRY)

#: The verdicts that are an absence of an answer. Same reason.
UNKNOWN_VERDICTS = (UNDATED, UNREADABLE)


# ------------------------------------------- DID THE WORK LAND, which is a
# ------------------------------------------- different question from the above
#
# WHY THIS IS SEPARATE FROM THE VERDICTS ABOVE. Those answer "had this work
# already landed BEFORE the dispatch". This answers "did THIS dispatch's work
# land at all", which only becomes a question when a dispatch was cut off.
#
# MEASURED 2026-10-16, TASK-0220. Six tasks were killed in one second, at
# 09:16:45, across six lanes. All six recorded the same `DONE` suffix and all
# six had an unreadable output file, and the outcomes were opposite:
#
#   suppression/0330   `exit-1`, `.out` 0 bytes, and a complete 3,085-word
#                      report in `LANE-suppression.md`, written by that very
#                      dispatch - absent from the `resonate-ops` snapshot
#                      taken before it and present in the one taken after
#   webapp/0190        `exit-1`, `.out` 0 bytes, no entry, no commit, and no
#                      file in its worktree with an mtime inside the window
#   pilotcaps/0241     `exit-1`, `.out` 0 bytes, no entry, no commit - and a
#                      34,712-byte untracked deliverable on disk, found an
#                      hour later by another lane, timestamped inside its
#                      window. Its REPORT died; its WORK did not
#
# So the exit code is a fact about the WRAPPER and not about the child:
# `src.lanes.DONE_MEANINGS` now says so for `exit-1`. And the output byte
# count is a fact about WHEN stdout was flushed - `claude -p` emits its
# result when it exits, so a killed child's file holds whatever the harness
# printed in the first seconds and nothing else. Neither is evidence here and
# neither is read below.
#
# THE SHAPE IS THE ONE `src.senderheadroom` ALREADY USES. LANDED is provable
# from ANY ONE positive authority. LOST is provable from NONE of them - it
# needs every authority READ AND EMPTY, and a reader who could not open one
# of them cannot reach it. NOT-DETERMINED is the default and is a state, not
# a rounding of the other two: `0170`'s lesson is that a zero which is a
# provable upper bound keeps the alarm and an UNKNOWN that throws the alarm
# away is worse, so this never renders as healthy and never renders as done.

#: Words under a heading before it counts as a REPORT rather than a bare
#: heading. 20, and it is a floor on nonsense rather than a quality bar: the
#: shortest real entry in this corpus on 2026-10-16 is `glm-c/0161`'s at 131
#: words and the longest is 3,477. A heading with fewer still counts as the
#: id being NAMED, which blocks LOST without licensing LANDED - the two
#: directions are not the same question and one number must not decide both.
MIN_ENTRY_BODY_WORDS = 20

#: One positive authority was read. The work is on the record somewhere.
LANDED = "landed"

#: Every authority was read and every one is empty. The work is gone.
LOST = "lost"

#: The default. At least one authority could not be read, so neither of the
#: other two is provable. NOT a synonym for LOST and NOT a synonym for DONE.
NOT_DETERMINED = "not_determined"

LANDING_ORDER = (LANDED, NOT_DETERMINED, LOST)

LANDING_TEXT = {
    LANDED: ("LANDED",
             "at least one positive authority was read: a lane-file entry "
             "that only this dispatch could have written, a commit inside "
             "this dispatch's own window, or a file in the lane's worktree "
             "timestamped inside it. One is sufficient; the others are not "
             "then needed"),
    NOT_DETERMINED: ("NOT DETERMINED",
                     "no positive authority fired AND at least one authority "
                     "could not be read, so this is neither done nor lost. "
                     "It is the honest state for a killed dispatch until "
                     "somebody walks that lane's worktree, and it is NOT "
                     "zero, NOT idle, NOT complete and NOT safe"),
    LOST: ("LOST",
           "every authority was read and every one came back empty: no "
           "entry names this id, no commit sits in the window, the "
           "worktree walk was PERFORMED and found nothing, and the brief is "
           "not queued again. Any one of those being unread makes this NOT "
           "DETERMINED instead"),
}

#: The `DONE` suffixes that mean the task was killed, so the suffix carries
#: no information about whether the work landed. A tuple rather than a
#: pattern: a suffix nobody has measured is not added on a guess.
#:
#: `TIMEOUT` JOINED IT ON 2026-10-16 AND THE GAP IT CLOSES IS THAT THE
#: QUESTION WAS NOT BEING ASKED. `row["landing"]` is computed only for a
#: suffix in this tuple, so until now a timed-out dispatch got
#: `landing: None` - no verdict at all, not even NOT DETERMINED. It was in
#: `src.lanes.DONE_MEANINGS` the whole time, which is why "TIMEOUT has no
#: entry" is the wrong diagnosis: it had a description and no mechanism.
#: `glm-c/0220` is the live row - 150.1 minutes, killed at the cap, nothing
#: in its `.out` after the banner.
#:
#: `exit1` IS DELIBERATELY NOT HERE. It means ran-and-failed, which is an
#: ordinary outcome with its own refusal predicate in `src.lanes`; asking the
#: landing question of all 17 of them would mean a `git log` per row for a
#: question they do not have. A bare `exit` is not here either, for the
#: opposite reason: those 15 lines are from 2026-10-15 and predate every
#: window this page can read.
KILLED_SUFFIXES = ("exit-1", "TIMEOUT")

# ----------------------------------------- the lane file's own clock
#
# THE FIFTH AUTHORITY, AND IT IS THE ONLY ONE THAT IS ASYMMETRIC BY DESIGN.
#
# `CONTINUITY.md` §3 licenses exactly one direction and this code may not
# widen it: *a lane's work is NOT proven landed by its LANE file's mtime, but
# an mtime older than the task's own START is real evidence the entry was
# never appended, because these files are appended to and not moved.*
#
# So the three states are NOT symmetric and must not be rendered as though
# they were:
#
#   mtime < START          NOT APPENDED. Positive evidence of absence. The
#                          file has not been touched since before this
#                          dispatch began, so nothing this dispatch did is
#                          in it.
#   START <= mtime <= DONE APPENDED DURING THE RUN. Positive evidence that
#                          something was written while this dispatch was
#                          alive - though not proof it was THIS dispatch, so
#                          it licenses LANDED only as one leg among five.
#   mtime > DONE           INCONCLUSIVE FOR THIS TASK. A later dispatch may
#                          have written it, and in the live instance one did:
#                          `LANE-glm-c.md` is 12:11:47 against a DONE of
#                          11:47:00. **This never renders as LANDED**, which
#                          is the sentence the brief asks to survive into the
#                          code.

LANE_MTIME_NOT_APPENDED = "not_appended"
LANE_MTIME_DURING = "appended_during_the_run"
LANE_MTIME_AFTER = "after_the_close"
LANE_MTIME_UNREAD = "unread"

LANE_MTIME_TEXT = {
    LANE_MTIME_NOT_APPENDED: (
        "NOT APPENDED",
        "the lane file's mtime is EARLIER than this dispatch's own START, so "
        "it has not been written since before the task began. These files "
        "are appended to and never moved, so this is real evidence that this "
        "dispatch put nothing in it - the one direction `CONTINUITY.md` §3 "
        "licenses"),
    LANE_MTIME_DURING: (
        "APPENDED DURING THE RUN",
        "the mtime falls inside this dispatch's START..DONE window, so "
        "something was written to the lane file while the task was alive. "
        "That is one leg of five and not a proof on its own: another lane "
        "does not share this file, but an earlier entry of this lane's could "
        "have been edited in the same window"),
    LANE_MTIME_AFTER: (
        "INCONCLUSIVE FOR THIS TASK",
        "the mtime is LATER than this dispatch's DONE, so a later task may "
        "have written it and this authority cannot say which did. It is read "
        "and it is inconclusive, which is not the same as unread and is "
        "NEVER a pass: a later mtime must not render as LANDED"),
    LANE_MTIME_UNREAD: (
        "UNREAD",
        "the lane file's mtime, this dispatch's START or its DONE could not "
        "be read, so the leg was not consulted at all. Distinct from "
        "INCONCLUSIVE, which IS a reading"),
}


def lane_mtime_leg(lane_mtime, start_when, done_when):
    """Which of the four states the lane file's clock is in, and the leg.

    Returns `(state, leg)` where `leg` is the tri-state this function
    contributes to `landing`: `True` only for APPENDED DURING THE RUN,
    `False` only for NOT APPENDED, and `None` for both of the other two.
    `None` never becomes `False` here either.
    """
    if lane_mtime is None or start_when is None:
        return LANE_MTIME_UNREAD, None
    if lane_mtime < start_when:
        return LANE_MTIME_NOT_APPENDED, False
    if done_when is None:
        # Still running, or a DONE this reader could not find. The file has
        # been touched since START and there is no upper bound to place it
        # against, so it is inconclusive rather than positive.
        return LANE_MTIME_AFTER, None
    if lane_mtime <= done_when:
        return LANE_MTIME_DURING, True
    return LANE_MTIME_AFTER, None

#: The four authorities, in the order the panel prints them, with what each
#: one is and the single reason it is NOT the others.
LANDING_AUTHORITIES = {
    "entry": ("LANE-<lane>.md, this dispatch's own entry",
              "a heading naming this TASK id with a report under it AND "
              "exactly one START line for the brief, so the entry can only "
              "have come from this dispatch. With two or more STARTs this "
              "leg is withheld rather than claimed - the entry may be an "
              "earlier run's, which is what `glm-c/0161` was"),
    "commit": ("a commit inside this dispatch's own START..DONE window",
               "`git log --all --reflog --since --until`, which reaches "
               "commits no branch tip reaches. It CANNOT reach a commit made "
               "on a detached HEAD in another worktree and then abandoned: "
               "that lives only in that worktree's own HEAD reflog"),
    "artefact": ("a file in the lane's worktree timestamped inside the window",
                 "the authority that refuted the two-leg version of this "
                 "test on `pilotcaps/0241`. It CANNOT be read from a page: "
                 "it needs a walk of THAT lane's worktree, which is another "
                 "lane's working state, and only a person standing in it can "
                 "answer"),
    "requeued": ("the brief queued again under its own number",
                 "read from the queue folders. A SUCCESSOR brief under a "
                 "different number - `0244` for `0241` - cannot be "
                 "identified mechanically and is not read here, so this leg "
                 "can only ever say 'not re-queued under its own number'"),
    "lane_mtime": ("the lane file's own clock against this dispatch's window",
                   "cheap, already on disk, and ASYMMETRIC by licence: an "
                   "mtime before START is real evidence nothing was "
                   "appended, an mtime inside the window is one positive "
                   "leg, and an mtime after DONE is read-and-inconclusive "
                   "because a later task may have written it. It can never "
                   "on its own make a row LANDED and it is the only leg that "
                   "can TAKE AWAY another one - see the interlock in "
                   "`landing`"),
}


def landing(entries, starts_for_task, commits_in_window=None,
            artefacts_in_window=None, requeued=None, lane_mtime_state=None,
            min_body_words=MIN_ENTRY_BODY_WORDS):
    """Did THIS dispatch's work land. Three states, and the default is the
    middle one.

    Every authority is TRI-STATE. `None` means "not read", and `None` never
    becomes `False`: that substitution is the whole defect this function
    exists to prevent, and it is `invariant 0` in `OPERATING-MODE` written
    out for one row of a table.

    `entries` is `entries_for(headings(text), task_id)`. An entry whose body
    is under `min_body_words` is a heading with nothing under it and does not
    count as a report - but it still counts as the id being NAMED, so it
    blocks LOST while not licensing LANDED.
    """
    reported = [item for item in entries
                if len(item["body"].split()) >= min_body_words]
    # LEG 1 HAS THREE ANSWERS AND THE MIDDLE ONE IS THE WHOLE POINT. An
    # entry alone proves the id was written about, not that THIS dispatch
    # wrote it, so a single START is required - and where there are two or
    # more the authority was READ and came back INCONCLUSIVE, which is None
    # and not False. The first version of this function returned False
    # there, and `glm-b/0170` rendered "entry: no" next to a 1,374-word
    # entry its third dispatch had written. That is the `None`-read-as-
    # `False` substitution this whole module exists to refuse, committed
    # inside the refusal.
    if starts_for_task is None:
        entry_leg = None
    elif not entries:
        # The only FALSE: no heading names this id, which is the authority
        # answering NO.
        entry_leg = False
    elif starts_for_task == 1 and reported:
        entry_leg = True
    else:
        # Either two or more dispatches, or a heading with nothing under it.
        # CAUGHT BY C3e: the first version returned `bool(reported)` here,
        # so a bare heading read as FALSE and a row with the id visibly on
        # the record reached LOST. A heading somebody wrote is a session that
        # got that far; it does not license LANDED and must not license LOST.
        entry_leg = None
    commit_leg = (None if commits_in_window is None
                  else bool(commits_in_window))
    artefact_leg = (None if artefacts_in_window is None
                    else bool(artefacts_in_window))
    requeued_leg = None if requeued is None else bool(requeued)

    # THE FIFTH LEG, AND THE ONE INTERLOCK IN THIS FUNCTION.
    #
    # `lane_mtime_state` arrives as one of the four `LANE_MTIME_*` words, or
    # None for unread, and its tri-state is derived here from the word rather
    # than passed in beside it - two representations of one fact is how the
    # two come to disagree.
    mtime_state = lane_mtime_state or LANE_MTIME_UNREAD
    mtime_leg = {LANE_MTIME_DURING: True,
                 LANE_MTIME_NOT_APPENDED: False}.get(mtime_state)

    # AND THE INTERLOCK: a lane file untouched since before START cannot
    # contain anything THIS dispatch wrote, so an entry in it must be an
    # earlier dispatch's and may not license LANDED for this one. The
    # demotion runs in ONE direction only - it can turn a True entry leg
    # into None and never the reverse - because the mtime is licensed as
    # evidence of absence and never as evidence of presence.
    demoted = False
    if mtime_leg is False and entry_leg is True:
        entry_leg = None
        demoted = True

    legs = {"entry": entry_leg, "commit": commit_leg,
            "artefact": artefact_leg, "requeued": requeued_leg,
            "lane_mtime": mtime_leg}

    if entry_leg or commit_leg or artefact_leg or mtime_leg:
        verdict = LANDED
    elif (entry_leg is False and commit_leg is False
          and artefact_leg is False and requeued_leg is False
          and mtime_leg is False):
        # Every authority read, every one empty. `entry_leg is False` means
        # no heading names this id AT ALL - a heading with an empty body is
        # the id being on the record, which is not nothing and does not
        # license this.
        verdict = LOST
    else:
        verdict = NOT_DETERMINED

    label, why = LANDING_TEXT[verdict]
    # WHICH AUTHORITY IS MISSING, by name, because "NOT DETERMINED" without
    # it is the same dead end as the UNKNOWN it replaces. Empty when the
    # verdict is LANDED: one positive authority makes the rest unneeded, and
    # listing them as missing would read as a weakness that is not there.
    unread = ([name for name in ("entry", "commit", "artefact", "requeued",
                                 "lane_mtime")
               if legs[name] is None]
              if verdict != LANDED else [])
    mtime_label, mtime_why = LANE_MTIME_TEXT[mtime_state]
    return {"verdict": verdict, "label": label, "why": why, "legs": legs,
            "unread": unread,
            "entries_naming_id": len(entries),
            "entries_with_a_report": len(reported),
            "starts_for_task": starts_for_task,
            "lane_mtime_state": mtime_state,
            "lane_mtime_label": mtime_label,
            "lane_mtime_why": mtime_why,
            # THE DEMOTION, PUBLISHED. A leg that was taken away silently is
            # a page that disagrees with its own evidence and will not say
            # why - and this one takes away the authority that fires most
            # often.
            "entry_demoted_by_mtime": demoted}


#: Seconds. The reflog walk is the slow half and the cap is what keeps a
#: render from hanging on it; the cheap walk never needs it.
COMMIT_WINDOW_TIMEOUT = 300


def commits_between(start_when, done_when, cwd=None, include_reflog=False,
                    timeout=None):
    """`(shas, complete)` for commits inside `start_when`..`done_when`.

    TWO TIERS, AND THE REASON IS A MEASUREMENT RATHER THAN A PREFERENCE.
    Timed in this repository on 2026-10-16 over the 08:35:24-09:16:45 window,
    both returning the same three commits:

        git log --all          --since --until      0.25 s
        git log --all --reflog --since --until     88.5 s

    88 seconds is the reflog walk across this repository's several hundred
    worktree branches. Six killed dispatches would make a page render take
    nine minutes, so the default walk is the cheap one.

    `complete` IS WHAT STOPS THAT BEING A LIE. The cheap walk reaches only
    what a ref reaches, and a commit a branch has since moved off is exactly
    `_STANDING-RULES.md`'s `0064` lesson - `glm/0055` kept its fix and lost
    its record, and the fix sat on a branch the worktree was not standing on.
    Over 09:18-10:45 the complete walk returns 14 commits of which 8 are
    reachable from no branch tip at all. So:

        a SHA found by either walk           proves work landed
        an EMPTY cheap walk                  proves NOTHING. complete=False
        an EMPTY complete walk               proves the window is empty

    `landing()` reads `None` as "not read", so the caller hands it
    `shas if complete else (shas or None)` and a cheap empty result can never
    reach LOST. That asymmetry is the same one `src.senderheadroom` already
    uses: a walk can only undercount, so presence is provable from any walk
    and absence only from a complete one.

    NEITHER WALK REACHES a commit made on a detached HEAD inside another
    worktree and then abandoned. That lives in
    `<git-common-dir>/worktrees/<name>/logs/HEAD`, a per-worktree reflog
    `--reflog` does not include, and reading it means opening the main
    checkout. It is named in `LANDING_AUTHORITIES` and is not closed here.

    `(None, False)` where either bound is missing or git declines.

    ONLY SHAS ARE READ BACK, deliberately: `subprocess` with `text=True`
    decodes in this machine's ANSI codepage and a commit subject carrying a
    non-ASCII byte comes back mojibake. A hex SHA cannot.
    """
    if start_when is None or done_when is None:
        return None, False
    args = ["log", "--all"]
    if include_reflog:
        args.append("--reflog")
    args += ["--format=%H",
             "--since=" + start_when.strftime("%Y-%m-%d %H:%M:%S"),
             "--until=" + done_when.strftime("%Y-%m-%d %H:%M:%S")]
    shown = _git(args, cwd,
                 COMMIT_WINDOW_TIMEOUT if timeout is None else timeout)
    if shown is None:
        return None, False
    return ([line.strip() for line in shown.splitlines() if line.strip()],
            bool(include_reflog))


def commit_leg(start_when, done_when, lane, known=(), cwd=None,
               include_reflog=False, branch_lanes=None, measured=None):
    """What `landing()` should be handed for the commit authority.

    The one place the `(shas, complete)` contract is turned into
    `landing()`'s tri-state, so no caller has to remember which empty means
    which. A list means READ; `None` means NOT READ.

    A WINDOW IS NOT AN ATTRIBUTION, and the first version of this leg forgot
    it. Six watchers run concurrently, so a 41-minute window contains other
    lanes' commits by default: `suppression/0330`'s window holds `1edcd1321`
    (pilotcaps' TASK 0239) and `8b2d12d11` (webapp's own 0180), and the leg
    reported LANDED-by-commit for `suppression` and for `pilotcaps/0241` off
    them. That is the identical defect `commit_only` carries a hard refusal
    for - `97fec582d` is "TASK 0170 (GLM-C)" and was once reported as
    evidence that `glm-b/0170` and `qwen/0170` had landed - so the refusal is
    reused here rather than re-derived.

    THE BAR IS A POSITIVE ATTRIBUTION, exactly as in `commit_only`: a commit
    counts only where every lane-named branch containing it names THIS lane.
    `branch_lanes_for` proves association and never authorship, so a commit
    reachable from two lanes' branches is NO INFORMATION and is dropped -
    which can only lose a positive and never invent one.

    A commit nothing can attribute leaves the leg EMPTY rather than
    unreadable, because the window itself was read. Where that happens and
    the walk was complete, the leg is a proven empty for THIS LANE.

    `measured` is the git seam, the same shape `commits_between` returns, so
    a test needs no repository - the module docstring's standing rule.
    """
    shas, complete = (
        measured if measured is not None
        else commits_between(start_when, done_when, cwd=cwd,
                             include_reflog=include_reflog))
    if shas is None:
        return None
    if shas:
        if branch_lanes is None:
            branch_lanes = branch_lanes_for(shas, known, cwd=cwd)
        mine = [sha for sha in shas
                if branch_lanes.get(sha) == [lane]]
        if mine:
            return mine
    return [] if complete else None


# ------------------------------------------------------- the dating ladder
#
# Four rungs, tried in this order, and the FIELD is reported with every
# answer. Rung names are the field names on purpose: a panel cell saying
# "re-dispatch" is worth nothing without the sentence that produced it.

#: `# 2026-10-16 02:01Z-02:11Z - TASK 0231`. The entry's own stated window.
#: The only rung that is trusted in BOTH directions, because it is the only
#: one whose meaning is unambiguous: the second time of a range is when the
#: run ended.
D_RANGE = "heading_time_range_end"

#: A commit SHA quoted inside the entry's own block whose commit MESSAGE
#: names this same TASK id, dated by git. Referential integrity in both
#: directions - the entry names the commit and the commit names the task.
#:
#: AND THE TASK NUMBER ALONE IS NOT ENOUGH, which cost this module seven
#: false positives on its first real run. Task numbers are per-lane and
#: commit messages are not: `38c0db9c4` is "TASK 0100 (GLM-C)" and the
#: `pilotcaps` lane quotes it inside its OWN `TASK 0100` entry, because
#: certifying another lane's commit is what that lane is for. Branch
#: reachability does not separate them either - that commit is reachable
#: from six branches, four of them `task-pilotcaps-*`, because pilotcaps
#: merged it to measure it.
#:
#: So an occurrence is REFUSED when a different lane is named either in the
#: commit's own subject or on the entry line that cites it. Absence of a
#: contrary attribution is the bar, which is weaker than a positive one, so
#: `lane_attribution` reports per row which of the three it is and the panel
#: prints the breakdown rather than one number. A SHA that does not resolve
#: here yields nothing rather than a failure: two of the sixteen in one
#: pilotcaps block do not.
D_COMMIT = "entry_commit_naming_task"

#: How strongly a convicting commit is tied to the lane whose entry quotes
#: it. Reported, never collapsed: a reader deciding whether to act on this
#: panel needs to know which rows rest on an absence.
A_SUBJECT = "positive_subject"       # the commit's own subject names this lane
A_BRANCHES = "positive_branches"     # the only lane-named branches are this one
A_UNCONTRADICTED = "not_contradicted"  # nothing names another lane. Weakest.

ATTRIBUTION_TEXT = {
    A_SUBJECT: "the commit's own subject names this lane",
    A_BRANCHES: ("every lane-named branch containing this commit names this "
                 "lane and no other"),
    A_UNCONTRADICTED: ("nothing in the commit subject, the citing line or "
                       "the branch set names another lane - an absence of a "
                       "contrary attribution, not a positive one"),
}

#: THE LANE'S OWN TESTIMONY, and it is the most direct evidence in the
#: corpus: `TASK 0020 RE-DISPATCHED - ALREADY DONE`, `TASK 0030 RE-DISPATCHED
#: (third run of this brief)`, `TASK 0010 re-dispatched by the watcher;
#: verified, not redone`. Not a dating inference at all - the session that
#: ran the brief says it found the work already there.
#:
#: IT IS NOT FIRST ON THE LADDER, deliberately. It is prose a model wrote
#: about its own situation, and a model can be wrong about that: pilotcaps
#: `0230`'s re-dispatch entry stamps itself 01:45Z-01:58Z, which is 76
#: seconds AFTER the START it is describing. So the two rungs that read a
#: clock are consulted first and this one decides only what they cannot -
#: and `rung_clashes` prints every case where they disagree.
#:
#: Applied ONLY to a task's LAST START. A declaration means the work existed
#: before the declaring run; with two STARTs the declaring run is the second
#: one and the first is a genuine first run. A declaring run later than the
#: last START is the one case this would get wrong, and it cannot happen: a
#: lane runs a brief it finds in its queue folder, and a dispatched brief has
#: been moved out of it.
D_DECLARED = "entry_declares_re_dispatch"

#: `## TASK 0050 - 2026-10-15 05:00`. A single bare time, and the corpus
#: uses this shape for a dispatch time (`21:07 dispatch`), a start time
#: (`01:30 watcher re-run`) and a close time, so it CANNOT be read as a
#: close time. It is used in one direction only: under every one of those
#: three readings, a value strictly before the START means the entry
#: describes a run that already existed when the watcher dispatched. It
#: never clears a START.
D_SINGLE = "heading_single_time"

#: The heading's date, bounded at the last instant of that day. Decides only
#: when the dates differ - an entry dated the day before a START closed
#: before it whatever the hour, and one dated the day after cannot have.
D_DATE = "heading_date"

#: Nothing on the ladder reached it.
D_NONE = "nothing_datable"

LADDER = (D_RANGE, D_COMMIT, D_SINGLE, D_DATE)

FIELD_TEXT = {
    D_RANGE: "the second time of the range in the entry's own heading",
    D_COMMIT: ("a commit quoted in the entry whose own message names this "
               "TASK id, dated by git's committer timestamp"),
    D_DECLARED: ("the entry's own heading says this run was a re-dispatch, "
                 "a second run, or that the work was already done"),
    D_SINGLE: ("the single time in the entry's heading, used only in the "
               "strictly-before direction because the corpus writes "
               "dispatch, start and close times all this way"),
    D_DATE: "the date in the entry's heading, bounded at end of day",
    D_NONE: "nothing in the entry carries a time, a date or a commit",
}


# ------------------------------------------------- where an entry sits in time

#: The entry is dated strictly before the START.
BEFORE = "before"

#: The entry is dated at or after the START.
AT_OR_AFTER = "at_or_after"

#: No rung reached this entry.
UNDATABLE = "undatable"


# ------------------------------------------------------------------ the shapes

#: An ISO date anywhere in a heading. Extracted and REMOVED before any time
#: is looked for, because `2026-10-15 23:04-23:55` holds three hyphens and a
#: range separator, and a reader that looks for the range first finds
#: `10-15`.
_DATE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")

#: One clock reading, in every shape this corpus writes:
#:
#:     05:00      exact
#:     ~01:40     approximate - the corpus means "about", never an hour out
#:     00:5x      the minute's tens digit only
#:     0?:??      unreadable, and it is a real heading in LANE-pilotcaps.md
#:     02:11Z     UTC, and the machine runs at +02:00
_TIME = re.compile(r"(?P<approx>~)?"
                   r"(?P<hh>\d{1,2}|\?{1,2})"
                   r":"
                   r"(?P<mm>\d{2}|\d[xX?]|\?{2})"
                   r"(?P<zulu>[Zz])?")

#: Hyphen, en dash and the unicode minus all appear as range separators in
#: this corpus (`23:04-23:55`, `05:55–06:05`). The em dash is the
#: heading's own field separator and is deliberately NOT one of these.
_RANGE_SEP = "[-–−]"

_RANGE = re.compile(_TIME.pattern + r"\s*" + _RANGE_SEP + r"\s*"
                    + _TIME.pattern.replace("(?P<", "(?P<b_"))

#: `TASK 0010`, `TASK-0130`, `TASK 0234c`, `TASK 1`. The trailing boundary is
#: the load-bearing part: without it `TASK 0234b` matches the id `0234`, and
#: `0234b` is a different brief with its own dispatch.
_HEAD_TASK = re.compile(r"(?i)\bTASKS?[\s\-:]*(\d{1,4}[a-z]?)(?![0-9A-Za-z])")

#: A markdown heading of any level. Lane files use `#` for a task entry in
#: `suppression` and `pilotcaps` and `##` in `webapp` and `glm-b`, so a
#: reader anchored on `##` finds nothing in two of the seven lanes.
_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")

#: `0234c-the-revert-that-rewrote-the-index.md` -> `0234c`.
_BRIEF_ID = re.compile(r"^(\d{1,4}[a-z]?)[-_]")

#: A session saying, in its own entry heading, that it found the work done.
#: Three shapes, all from the real corpus, and every match is printed with
#: its heading so the declaration can be read rather than trusted.
_DECLARES = (
    re.compile(r"(?i)\bre-?dispatch(?:ed)?\b"),
    re.compile(r"(?i)\b(?:second|third|fourth|2nd|3rd|4th)\s+"
               r"(?:dispatch|run|pass|observer)\b"),
    re.compile(r"(?i)\balready\s+(?:done|built|landed|have\s+entries)\b"),
)

#: ...and the shapes that LOOK like a declaration and are not. `0040`'s
#: heading reads "re-dispatch after glm-b's 0040 lands", which is a
#: recommendation about the future, not a report about this run.
_NOT_A_DECLARATION = re.compile(r"(?i)\bre-?dispatch\s+"
                                r"(?:after|when|once|if|unless)\b")

#: A candidate commit SHA. Nine is the shortest this corpus writes. Pure
#: digits are excluded because a nine-digit number is a number, and the
#: 32-character case is excluded because that is an md5 and this estate
#: quotes a great many of them.
_SHA = re.compile(r"\b(?=[0-9a-f]*[a-f])[0-9a-f]{9,40}\b")

#: Hours. `src.lanes` owns this because the same question - what is this
#: machine's offset from UTC - is already answered there for the provider
#: clock, and two answers to one question is how they drift.
_UTC = "utc"

MAX_LANE_FILE_BYTES = 8 * 1024 * 1024

#: SHAs per `git` invocation. Windows caps a command line near 32767 bytes
#: and a 40-character SHA plus a space is 41, so 200 is two orders of
#: magnitude inside it and still batches the whole estate in a few calls.
SHA_BATCH = 200


# ------------------------------------------------------------- the time reader


def _bound(match, prefix=""):
    """The LAST instant a clock reading could name, as `(h, m, s, utc)`.

    `None` when the hour is unreadable. The upper bound is deliberate: every
    comparison below asks "is this before the START", so bounding a fuzzy
    reading at its latest possible instant can only ever UNDER-report a
    re-dispatch. A tilde is bounded at the end of its hour, which is far
    more slack than "about" ever means here and still leaves `~01:40Z`
    (03:59:59 local) two and a half hours clear of the 06:38:51 START it
    convicts.
    """
    hour = match.group(prefix + "hh")
    if not hour.isdigit():
        return None
    hour = int(hour)
    if hour > 23:
        return None
    minute = match.group(prefix + "mm")
    if match.group(prefix + "approx"):
        # "about 01:40" is bounded at 01:59:59, not at 01:40:59.
        return hour, 59, 59, bool(match.group(prefix + "zulu"))
    if minute.isdigit():
        value = int(minute)
        if value > 59:
            return None
        return hour, value, 59, bool(match.group(prefix + "zulu"))
    if minute[0].isdigit():
        # `5x` - the tens digit is stated, so the latest is `59`.
        return hour, int(minute[0]) * 10 + 9, 59, \
            bool(match.group(prefix + "zulu"))
    # `??` - the hour is stated and the minute is not.
    return hour, 59, 59, bool(match.group(prefix + "zulu"))


def _at(day, bound, offset_hours):
    """A naive LOCAL datetime for `bound` on `day`, or None.

    The watcher's own stamps carry no offset and `src.lanes` refuses to
    guess one for them. A `Z` in a lane heading is not a guess - the author
    wrote it - so it is converted, using the one offset reader this
    repository already has.
    """
    if day is None or bound is None:
        return None
    hour, minute, second, utc = bound
    when = datetime.datetime(day.year, day.month, day.day, hour, minute,
                             second)
    if utc:
        if offset_hours is None:
            return None
        when += datetime.timedelta(hours=offset_hours)
    return when


def parse_heading(text, day_hint=None, offset_hours=None):
    """What a lane-file heading says about WHEN, and which field said it.

    Returns a dict with `task_ids`, `date`, `range_end`, `single` and
    `shape`. Everything is `None` when the heading does not carry it; an
    unreadable reading (`0?:??`) is `None` too, and the caller cannot tell
    those apart because it does not need to - both fall through the same
    rung.
    """
    out = {"task_ids": [], "date": None, "range_end": None, "single": None,
           "shape": None, "dates_seen": 0}
    for match in _HEAD_TASK.finditer(text):
        token = normalise_id(match.group(1))
        if token not in out["task_ids"]:
            out["task_ids"].append(token)

    dates = _DATE.findall(text)
    out["dates_seen"] = len(dates)
    day = None
    if dates:
        # The FIRST date, which is the entry's claimed date. A heading
        # reading `2026-10-16 (started 2026-10-15 late)` carries two and the
        # second is a parenthetical about the run, not the entry's date.
        try:
            day = datetime.date(int(dates[0][0]), int(dates[0][1]),
                                int(dates[0][2]))
        except ValueError:
            day = None
    if day is None:
        day = day_hint
    out["date"] = day

    rest = _DATE.sub(" ", text)
    found = _RANGE.search(rest)
    if found:
        out["shape"] = "range"
        start_bound = _bound(found)
        end_bound = _bound(found, "b_")
        if end_bound is not None:
            # A range is UTC when EITHER end is marked. `02:01Z-02:11Z`
            # marks both; nothing in the corpus marks only the second.
            if start_bound is not None and start_bound[3]:
                end_bound = end_bound[:3] + (True,)
            end = _at(day, end_bound, offset_hours)
            if (end is not None and start_bound is not None
                    and _at(day, start_bound, offset_hours) is not None
                    and end < _at(day, start_bound, offset_hours)):
                # `23:57-00:0x` - the run crossed midnight, so the range's
                # end is on the next day. Not a typo and not discarded.
                end += datetime.timedelta(days=1)
            out["range_end"] = end
        return out

    found = _TIME.search(rest)
    if found:
        out["shape"] = "single"
        out["single"] = _at(day, _bound(found), offset_hours)
    return out


def normalise_id(token):
    """`0010` and `10` are the same brief; `0234` and `0234c` are not.

    Leading zeros go because the corpus writes both `TASK 0010` and
    `TASK 10`. The letter stays, lowercased, because `0234b` is a separate
    file with a separate dispatch and a separate 90-minute budget.
    """
    token = (token or "").strip().lower()
    match = re.match(r"^0*(\d+)([a-z]?)$", token)
    if not match:
        return token
    return match.group(1) + match.group(2)


def brief_id(filename):
    """The TASK id a brief filename carries, or None.

    NEVER used as the test for whether work is done - the brief is explicit
    that filename equality is not task equality - only to name the id whose
    entries are then looked for.
    """
    match = _BRIEF_ID.match(os.path.basename(filename or ""))
    return normalise_id(match.group(1)) if match else None


# -------------------------------------------------------------- the lane file


def headings(text, offset_hours=None):
    """Every heading in a lane file, with its block, in file order.

    The BLOCK matters because rung `D_COMMIT` reads SHAs out of the entry's
    own body and must not reach into the next entry's: `282b22658` is
    "TASK 0231 re-dispatch" and it is quoted inside the 0234 entry.
    """
    lines = text.splitlines()
    found = []
    for index, line in enumerate(lines):
        match = _HEADING.match(line)
        if match:
            found.append({"line": index + 1, "level": len(match.group(1)),
                          "text": match.group(2).strip()})
    for position, item in enumerate(found):
        # The block ends at the next heading of the SAME level or higher.
        # Deeper sub-headings belong to this entry; `### Addendum` inside a
        # `##` entry is that entry's own words.
        end = len(lines)
        for later in found[position + 1:]:
            if later["level"] <= item["level"]:
                end = later["line"] - 1
                break
        item["block_end"] = end
        item["body"] = "\n".join(lines[item["line"]:end])
        item.update(parse_heading(item["text"], offset_hours=offset_hours))
    return found


def entries_for(found, task_id):
    """The headings whose own text names this TASK id as a subject.

    Keyed on the id and not the filename, which is what the brief asks for,
    and the id is compared for EQUALITY after normalisation rather than by
    containment. `TASK 0234b` does not answer for `0234`.
    """
    return [item for item in found if task_id in item["task_ids"]]


def _read_text(path):
    """`(state, text)`. Four states, and three of them are not prose."""
    if not os.path.exists(path):
        return lanes.ABSENT, ""
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as handle:
            blob = handle.read(MAX_LANE_FILE_BYTES)
    except OSError:
        return lanes.UNREADABLE, ""
    text = blob.decode("utf-8", "replace")
    if text.startswith("﻿"):
        text = text[1:]
    if not text.strip():
        return lanes.EMPTY, text
    if size > MAX_LANE_FILE_BYTES:
        # Truncated rather than refused - but SAID, because an entry past
        # the cut is indistinguishable from an entry that was never written
        # and that is exactly the confusion this module exists to stop.
        return lanes.PRESENT, text
    return lanes.PRESENT, text


# ------------------------------------------------------------------ the git seam
#
# One callable, injected. A test presents a dict and needs no repository; a
# platform with no `git` on the path degrades to "the rung reached nothing"
# rather than to an exception on a page request.


def git_commits(shas, cwd=None, timeout=60):
    """`{sha: {"when": local datetime, "subject": str}}` for what resolves.

    Two reads, never a write. `cat-file --batch-check` first because it
    answers "missing" for a token that is not an object instead of failing
    the whole batch, and a lane file quotes plenty of hex that is not a
    commit.
    """
    shas = sorted(set(shas))
    if not shas:
        return {}
    resolved = {}
    for chunk in [shas[i:i + SHA_BATCH]
                  for i in range(0, len(shas), SHA_BATCH)]:
        check = _git(["cat-file", "--batch-check"], cwd, timeout,
                     stdin="\n".join(chunk) + "\n")
        if check is None:
            return {}
        keep = []
        for line in check.splitlines():
            parts = line.split()
            if len(parts) >= 2 and parts[1] == "commit":
                keep.append(parts[0])
        if not keep:
            continue
        shown = _git(["log", "--no-walk", "--format=%H%x09%cd%x09%s",
                      "--date=format-local:%Y-%m-%d %H:%M:%S"] + keep,
                     cwd, timeout)
        if shown is None:
            continue
        for line in shown.splitlines():
            parts = line.split("\t", 2)
            if len(parts) != 3:
                continue
            try:
                when = datetime.datetime.strptime(parts[1],
                                                  "%Y-%m-%d %H:%M:%S")
            except ValueError:
                continue
            resolved[parts[0]] = {"when": when, "subject": parts[2]}
    # Abbreviations are what the lane files actually quote, so every
    # resolved full SHA is also keyed by each abbreviation that asked for it.
    out = {}
    for sha in shas:
        for full, row in resolved.items():
            if full.startswith(sha.lower()):
                out[sha] = row
                break
    return out


def _git(args, cwd, timeout, stdin=None):
    """Stdout, or None. A git that is absent or angry is UNKNOWN, not zero."""
    try:
        done = subprocess.run(["git"] + list(args), cwd=cwd, timeout=timeout,
                              input=stdin, capture_output=True, text=True)
    except (OSError, subprocess.SubprocessError):
        return None
    if done.returncode != 0:
        return None
    return done.stdout


def lane_tokens(text, lane, known):
    """The lanes `text` names, longest name first, excluding `lane` itself.

    LONGEST FIRST IS LOAD-BEARING. `glm` is a prefix of `glm-b` and `glm-c`,
    so a reader that matches `glm` first reads `task-glm-c-2026-10-14` as
    the `glm` lane's own branch and accepts a commit that belongs to a
    different lane. Matched tokens are blanked as they are found, so the
    shorter name cannot then match the remainder.
    """
    lowered = (text or "").lower()
    out = []
    for name in sorted(known, key=len, reverse=True):
        # The trailing boundary must NOT exclude a hyphen. Every branch in
        # this estate is `task-<lane>-<date>`, so `glm-c` is always followed
        # by one, and a lookahead of `(?![0-9a-z-])` matched none of them -
        # which made the whole cross-lane refusal silently inert on the one
        # input shape it exists for. Longest-name-first plus the blanking
        # below is what stops `glm` matching inside `glm-c`, not this.
        pattern = re.compile(r"(?<![0-9a-z])" + re.escape(name.lower())
                             + r"(?![0-9a-z])")
        if pattern.search(lowered):
            lowered = pattern.sub(" " * len(name), lowered)
            if name != lane:
                out.append(name)
    return out


def _occurrence_lines(body, sha):
    """Every line of the entry body that cites this SHA."""
    return [line for line in body.splitlines() if sha in line]


def _commit_rung(entry, task_id, commits, lane=None, known=(),
                 branch_lanes=None):
    """The earliest commit in this entry that is THIS lane's own, or None.

    EARLIEST, not latest: the question is when the work first landed, and an
    entry that quotes both its own first-run commit and its re-dispatch
    commit is the re-dispatch signal rather than a false positive.

    Three conditions, and the second and third exist because the first alone
    convicted seven innocent STARTs:

    1. the commit's own subject names this TASK id;
    2. the commit's subject names no OTHER lane;
    3. at least one line of the entry citing the SHA names no other lane.

    `known` is the lane list. When it is empty, conditions 2 and 3 cannot be
    evaluated and the rung still answers - this is a deliberate choice for a
    fixture that has no estate, and the real panel always passes the list.
    """
    best = None
    for sha in set(_SHA.findall(entry["body"])):
        row = commits.get(sha)
        if not row:
            continue
        named = [normalise_id(m.group(1))
                 for m in _HEAD_TASK.finditer(row["subject"])]
        if task_id not in named:
            continue

        subject_other = lane_tokens(row["subject"], lane, known)
        if subject_other:
            continue
        lines = _occurrence_lines(entry["body"], sha)
        clean = [line for line in lines
                 if not lane_tokens(line, lane, known)]
        if lines and not clean:
            continue

        # Positive attribution, strongest first. Never used to refuse -
        # refusals are conditions 2 and 3 above - only to say how much of
        # this row rests on an absence.
        attribution = A_UNCONTRADICTED
        if lane and lane in lane_tokens(row["subject"], None, known):
            attribution = A_SUBJECT
        elif branch_lanes is not None:
            seen = branch_lanes.get(sha)
            if seen is not None and set(seen) == {lane}:
                attribution = A_BRANCHES
            elif seen and lane not in seen:
                # Every lane-named branch holding it names someone else.
                continue

        if best is None or row["when"] < best["when"]:
            best = {"sha": sha, "when": row["when"],
                    "subject": row["subject"], "attribution": attribution,
                    "cited_on": (clean or lines or [""])[0].strip()}
    return best


def declares(text):
    """Does this heading say, of itself, that the work was already done?

    The negative pattern is checked FIRST and wins. `0040`'s heading says
    "re-dispatch after glm-b's 0040 lands", which is a request for a future
    dispatch; reading it as a report about this run would convict a START
    whose work had not landed at all.
    """
    if _NOT_A_DECLARATION.search(text or ""):
        return False
    return any(pattern.search(text or "") for pattern in _DECLARES)


def place_entry(entry, task_id, start_when, commits, lane=None, known=(),
                branch_lanes=None):
    """Where one entry sits relative to a START, and which field said so.

    `(position, field, value, detail, attribution)`. The ladder is tried in
    order and the first rung that reaches an answer is the one reported - but
    EVERY rung is computed, so `disagreements()` can cross them.
    """
    rungs = rung_readings(entry, task_id, start_when, commits, lane=lane,
                          known=known, branch_lanes=branch_lanes)
    for field in LADDER:
        reading = rungs.get(field)
        if reading and reading["position"] != UNDATABLE:
            return (reading["position"], field, reading["value"],
                    reading.get("detail"), reading.get("attribution"))
    return UNDATABLE, D_NONE, None, None, None


def rung_readings(entry, task_id, start_when, commits, lane=None, known=(),
                  branch_lanes=None):
    """Every rung's answer for one entry, whether or not it is the one used."""
    out = {}

    end = entry.get("range_end")
    if end is not None:
        out[D_RANGE] = {"value": end, "detail": entry["text"],
                        "position": BEFORE if end < start_when
                        else AT_OR_AFTER}

    found = _commit_rung(entry, task_id, commits, lane=lane, known=known,
                         branch_lanes=branch_lanes)
    if found:
        out[D_COMMIT] = {
            "value": found["when"],
            "detail": "%s  %s" % (found["sha"], found["subject"]),
            "attribution": found["attribution"],
            "position": BEFORE if found["when"] < start_when
            else AT_OR_AFTER}

    single = entry.get("single")
    if single is not None:
        # ONE DIRECTION ONLY. A single bare time names a dispatch in
        # `21:07 dispatch`, a start in `01:30 watcher re-run` and a close
        # elsewhere, and under all three a value before the START means the
        # entry is about an earlier run. A value after it means nothing,
        # so it reports AT_OR_AFTER - which clears nothing on its own,
        # because `FRESH` requires no UNDATABLE entry and this rung never
        # produces one.
        out[D_SINGLE] = {"value": single, "detail": entry["text"],
                         "position": BEFORE if single < start_when
                         else AT_OR_AFTER}

    day = entry.get("date")
    if day is not None:
        if day < start_when.date():
            out[D_DATE] = {"value": datetime.datetime(
                day.year, day.month, day.day, 23, 59, 59),
                "detail": entry["text"], "position": BEFORE}
        elif day > start_when.date():
            out[D_DATE] = {"value": datetime.datetime(
                day.year, day.month, day.day, 0, 0, 0),
                "detail": entry["text"], "position": AT_OR_AFTER}
        else:
            out[D_DATE] = {"value": None, "detail": entry["text"],
                           "position": UNDATABLE}
    return out


def classify(task_id, start_when, found, commits, brief_mtime=None,
             lane=None, known=(), branch_lanes=None, declared_allowed=True):
    """One START's verdict, with the entry and the field that produced it.

    TWO INDEPENDENT QUESTIONS, and the first version of this function put
    them on one ladder and lost four real re-dispatches to it. The dating
    ladder asks WHEN an entry closed. The declaration asks whether the run
    that wrote the entry found the work already there. They are not
    comparable, and a re-dispatch entry answers them in opposite directions
    by construction: `TASK 0030 RE-DISPATCHED (third run of this brief)`
    carries the range `22:09-22:40`, which is correctly AT OR AFTER its own
    START of 22:09:20 and says nothing at all about the two runs before it.

    So the roll-up is:

    - ANY entry dated before the START confirms a re-dispatch. One proof is
      a proof; the other entries' datability cannot take it away.
    - Otherwise ANY entry DECLARING itself a re-dispatch confirms one, when
      this is the task's last START. The declaration is reported second
      because it is prose and the clock rungs are not.
    - Otherwise ANY undatable entry makes the whole START UNKNOWN. This is
      the fail-closed rung and the one `C4` exists to hold: an entry nothing
      dates must never be read as an entry that closed after the dispatch.
    - Otherwise every entry is positively dated at or after the START, so the
      dispatch produced them: FRESH.
    - No entry at all is NO_ENTRY, which is not a re-dispatch and not
      UNKNOWN. The authority is readable and it answers.
    """
    entries = entries_for(found, task_id)
    row = {"task": task_id, "start": start_when, "verdict": None,
           "field": D_NONE, "value": None, "entry": None, "detail": None,
           "entries": len(entries), "rewritten": False, "placements": [],
           "attribution": None}
    if not entries:
        row["verdict"] = NO_ENTRY
        return row

    best = None
    declared = None
    undatable = False
    for entry in entries:
        position, field, value, detail, attribution = place_entry(
            entry, task_id, start_when, commits, lane=lane, known=known,
            branch_lanes=branch_lanes)
        row["placements"].append({"line": entry["line"], "position": position,
                                  "field": field, "value": value,
                                  "text": entry["text"]})
        # The declaration is read off EVERY entry regardless of where the
        # dating ladder put that entry, because the two answer different
        # questions. Collected here rather than in `place_entry` so it can
        # never displace a clock reading.
        if (declared is None and declared_allowed
                and declares(entry["text"])):
            declared = entry
        if position == UNDATABLE:
            undatable = True
            continue
        if position != BEFORE:
            continue
        if best is None or value < best[2]:
            best = (entry, field, value, detail, attribution)

    if best is not None:
        entry, field, value, detail, attribution = best
        row.update({"verdict": REWORK, "field": field, "value": value,
                    "entry": entry["line"], "detail": detail,
                    "attribution": attribution})
        # Blind spot 2, priced per row rather than argued: an entry that
        # predates the START proves nothing if the BRIEF was rewritten after
        # that entry was written. Flagged, never silently counted.
        if brief_mtime is not None and brief_mtime > value:
            row["rewritten"] = True
        return row

    if declared is not None:
        # No clock reached it and the lane said so itself. `value` stays
        # None - a declaration carries no time, and inventing one would put
        # a number on the panel that no field produced.
        row.update({"verdict": REWORK, "field": D_DECLARED, "value": None,
                    "entry": declared["line"], "detail": declared["text"]})
        return row

    row["verdict"] = UNDATED if undatable else FRESH
    if not undatable and row["placements"]:
        first = row["placements"][0]
        row["field"] = first["field"]
        row["value"] = first["value"]
        row["entry"] = first["line"]
    return row


# ------------------------------------------------------------------- the cost


def _closing(events, index):
    """The DONE that closes the START at `index`, or None.

    Paired by TASK NAME forward from this START and stopped at the next
    START of the same task, so a brief dispatched twice does not borrow the
    other run's clock. `src.lanes.task_durations` pairs by name across the
    whole log, which is right for a median and wrong here.
    """
    task = events[index]["task"]
    for event in events[index + 1:]:
        if event.get("task") != task:
            continue
        if event["kind"] == "done":
            return event
        if event["kind"] == "start":
            return None
    return None


# ------------------------------------------------------------------ the panel


def branch_lanes_for(shas, known, cwd=None, timeout=120):
    """`{sha: [lanes named by the branches containing it]}`.

    A POSITIVE attribution signal and nothing else. It is not a refusal on
    its own: `38c0db9c4` is reachable from four `task-pilotcaps-*` branches
    AND from `task-glm-c-2026-10-14`, because pilotcaps merged glm-c's work
    in order to certify it - so containment proves association, never
    authorship. A commit every lane-named branch attributes to ONE lane is
    the only case this answers usefully, and the caller treats anything else
    as no information.
    """
    out = {}
    for sha in sorted(set(shas)):
        shown = _git(["for-each-ref", "--format=%(refname:short)",
                      "--contains", sha], cwd, timeout)
        if shown is None:
            continue
        seen = []
        for ref in shown.splitlines():
            for name in lane_tokens(ref, None, known):
                if name not in seen:
                    seen.append(name)
        out[sha] = seen
    return out


def clock_controls(rows=None):
    """Three checks on the lane-file-clock leg, run on every render.

    C4 of TASK 0250 is a REFUSAL rather than a warning: the renderer does not
    print the clock column at all unless every check below has been seen
    producing BOTH of its states, and unless at least one cell in the table
    it is about to print reads UNREAD. A board with no UNREAD anywhere is a
    board that is guessing, and this leg's whole purpose is to keep an
    inconclusive reading visible.

    `rows` is the killed-dispatch rows about to be rendered, for the last
    check only. Passing None skips it and says so.
    """
    checks = []
    start = datetime.datetime(2026, 10, 16, 9, 16, 52)
    done = datetime.datetime(2026, 10, 16, 11, 47, 0)

    # C1: NOT APPENDED, from an mtime before START.
    state, leg = lane_mtime_leg(start - datetime.timedelta(minutes=5),
                                start, done)
    ok1 = state == LANE_MTIME_NOT_APPENDED and leg is False
    checks.append({
        "name": "the clock leg can print NOT APPENDED",
        "ok": ok1,
        "detail": ("an mtime five minutes before START reads %s, leg %s"
                   % (LANE_MTIME_TEXT[state][0], leg)),
    })

    # C2: APPENDED DURING THE RUN, from an mtime inside the window. The live
    # row cannot supply this leg - `glm-c/0220`'s lane file is 12:11:47
    # against a DONE of 11:47:00, which is INCONCLUSIVE - so the fixture is
    # constructed, which is what the brief asks for when the real row does
    # not confirm.
    state, leg = lane_mtime_leg(start + datetime.timedelta(minutes=30),
                                start, done)
    ok2 = state == LANE_MTIME_DURING and leg is True
    checks.append({
        "name": "the clock leg can print APPENDED DURING THE RUN",
        "ok": ok2,
        "detail": ("an mtime thirty minutes after START and before DONE "
                   "reads %s, leg %s" % (LANE_MTIME_TEXT[state][0], leg)),
    })

    # C2b, mine rather than the brief's: the asymmetry itself. An mtime
    # after DONE must be read-and-inconclusive and must never contribute a
    # positive leg. This is the one sentence the brief asks to survive into
    # the code, so it is asserted on every render and not only in a test.
    state, leg = lane_mtime_leg(done + datetime.timedelta(minutes=25),
                                start, done)
    ok2b = state == LANE_MTIME_AFTER and leg is None
    checks.append({
        "name": "an mtime after DONE never contributes a positive leg",
        "ok": ok2b,
        "detail": ("an mtime twenty-five minutes after DONE reads %s, leg "
                   "%s - which is the live state of `glm-c/0220`"
                   % (LANE_MTIME_TEXT[state][0], leg)),
    })

    # C3 of the brief, on the leg's own terms: the UNREAD state has to be
    # reachable, and reachable DIFFERENTLY from INCONCLUSIVE.
    state, leg = lane_mtime_leg(None, start, done)
    ok3 = state == LANE_MTIME_UNREAD and leg is None
    checks.append({
        "name": "an unreadable mtime is UNREAD and not INCONCLUSIVE",
        "ok": ok3,
        "detail": ("a missing mtime reads %s, leg %s, which is a different "
                   "word from the after-DONE case and has a different "
                   "repair" % (LANE_MTIME_TEXT[state][0], leg)),
    })

    # AND THE ONE ABOUT THE TABLE ITSELF.
    if rows is None:
        checks.append({
            "name": "at least one rendered cell reads UNREAD",
            "ok": False,
            "detail": ("the rows were not passed to this check, so it could "
                       "not look. Not a pass"),
        })
    else:
        unread = [row for row in rows
                  if any(value is None
                         for value in (row.get("landing") or {})
                         .get("legs", {}).values())]
        checks.append({
            "name": "at least one rendered cell reads UNREAD",
            "ok": bool(unread),
            "detail": ("%d of %d killed rows carry at least one UNREAD leg. "
                       "A table with none is a board that is guessing: the "
                       "worktree leg CANNOT be read from a page, so a row "
                       "without an UNREAD has had a refusal quietly turned "
                       "into an answer" % (len(unread), len(rows))),
        })
    return checks


def lane_rework(root, lane, commits=None, offset_hours=None, cwd=None,
                known=(), branch_lanes=None, include_reflog=False):
    """One lane's rows and totals. Every ratio carries its denominator.

    A lane whose log cannot be read returns `state=UNREADABLE` and NO rows,
    and its counts are `None` rather than `0`. `pilotcaps/0235` exists
    because three figures in one run were wrong and one of them was a count
    divided by rows; so `starts` here is the number of START lines and
    nothing else is divided by anything else.
    """
    log_path = os.path.join(root, "logs", "watcher-%s.log" % lane)
    lane_path = os.path.join(root, "LANE-%s.md" % lane)

    out = {"lane": lane, "state": None, "log_state": None,
           "lane_file_state": None, "rows": [], "starts": None,
           "tally": {}, "minutes": None, "minutes_unknown": 0,
           "unpriced": [], "truncated": False, "offset_hours": offset_hours,
           "entry_rungs": [], "landing_tally": {}}

    log_state, lines, truncated = lanes._read_tail(log_path)
    out["log_state"] = log_state
    out["truncated"] = truncated
    lane_state, text = _read_text(lane_path)
    out["lane_file_state"] = lane_state

    # THE LANE FILE'S OWN CLOCK, read ONCE per lane rather than per row. It
    # is one number for the whole file - these are append-only, so every row
    # in this lane is placed against the same mtime - and reading it per row
    # would be a `stat` per START for a figure that cannot differ between
    # them. An unreadable mtime is None and the leg then says UNREAD.
    try:
        out["lane_file_mtime"] = datetime.datetime.fromtimestamp(
            os.path.getmtime(lane_path))
    except OSError:
        out["lane_file_mtime"] = None

    if log_state in (lanes.ABSENT, lanes.UNREADABLE, lanes.EMPTY):
        out["state"] = UNREADABLE
        return out
    if lane_state in (lanes.ABSENT, lanes.UNREADABLE):
        # The log is readable and the authority it must be crossed against
        # is not. That is UNKNOWN for every cell, not "no entries found".
        #
        # ABSENT COUNTS, and it is the case that nearly shipped wrong. A
        # lane file that is not there cannot answer "did an entry exist",
        # and reading its absence as "no entry existed" would hand every
        # START in the lane a clean verdict off a missing authority. An
        # EMPTY lane file is different and is NOT here: it exists and holds
        # nothing, which is an authority answering, so its STARTs are
        # NO_ENTRY. Three states, three facts, the same discipline
        # `src.lanes._read_tail` already keeps.
        out["state"] = UNREADABLE
        return out

    out["state"] = lanes.PRESENT
    found = headings(text, offset_hours=offset_hours)
    events = lanes.watcher_events(lines, lane)
    starts = [(index, event) for index, event in enumerate(events)
              if event["kind"] == "start"]
    out["starts"] = len(starts)

    if commits is None:
        commits = git_commits(_candidate_shas(found), cwd=cwd)
        if branch_lanes is None and known:
            # Only the SHAs that could convict - a subject naming some task
            # id. Containment is the expensive read here, so it is not run
            # over the hundreds of hashes a lane file quotes for other
            # reasons.
            branch_lanes = branch_lanes_for(
                [sha for sha, row in commits.items()
                 if _HEAD_TASK.search(row["subject"])], known, cwd=cwd)

    # Which START is each task's LAST one. The declaration rung is allowed
    # only there: a declaration says the work existed before the declaring
    # run, and with two dispatches of one brief the declaring run is the
    # second, so convicting the first on it would be wrong.
    last_start = {}
    # HOW MANY TIMES THIS LANE DISPATCHED EACH ID, which is the second half
    # of `landing()`'s entry leg: an entry proves the id was written about,
    # and only a SINGLE dispatch proves this dispatch wrote it.
    starts_per_task = {}
    for index, event in starts:
        task = brief_id(event["task"])
        if task:
            last_start[task] = index
            starts_per_task[task] = starts_per_task.get(task, 0) + 1

    minutes = 0.0
    for index, event in starts:
        task = brief_id(event["task"])
        if task is None:
            # A START line whose filename carries no leading number. Not
            # classifiable, and it is not FRESH either.
            row = {"task": None, "start": event["when"], "verdict": UNDATED,
                   "field": D_NONE, "value": None, "entry": None,
                   "detail": None, "entries": 0, "rewritten": False,
                   "placements": [], "attribution": None}
        else:
            row = classify(task, event["when"], found, commits,
                           brief_mtime=_brief_mtime(root, lane,
                                                    event["task"]),
                           lane=lane, known=known,
                           branch_lanes=branch_lanes,
                           declared_allowed=last_start.get(task) == index)
        row["brief"] = event["task"]
        row["at"] = event["at"]
        closing = _closing(events, index)
        row["done"] = closing["at"] if closing else None
        row["done_suffix"] = closing.get("suffix") if closing else None
        seconds = (lanes._seconds_between(event["when"], closing["when"])
                   if closing else None)
        row["minutes"] = (seconds / 60.0
                          if seconds is not None and seconds >= 0 else None)

        # DID THIS DISPATCH'S WORK LAND. Computed only where the suffix says
        # the wrapper was killed, which is the only case where the question
        # is open: `exit0` already proves the lane file grew and a refusal
        # already has its own three-state answer in `src.lanes`. Doing it for
        # every START would also mean a `git log` per START - 178 of them in
        # this estate on 2026-10-16 - for a question 6 of them have.
        row["landing"] = None
        if row["done_suffix"] in KILLED_SUFFIXES:
            row["landing"] = landing(
                entries_for(found, task) if task else [],
                starts_per_task.get(task),
                commits_in_window=commit_leg(
                    event["when"], closing["when"] if closing else None,
                    lane, known=known, cwd=cwd,
                    include_reflog=include_reflog),
                # NEVER READ HERE, and the None is the point. The walk needs
                # this lane's own worktree, and a worktree is another lane's
                # working state - `_STANDING-RULES.md` forbids entering one
                # and this page would be doing it on every render. So the
                # authority that refuted the two-leg test on `pilotcaps/0241`
                # is named as unread rather than assumed empty, and LOST stays
                # out of reach from here BY CONSTRUCTION.
                artefacts_in_window=None,
                requeued=_requeued(root, lane, event["task"]),
                # THE FIFTH LEG. The state is computed here, where both ends
                # of this dispatch's window are in hand, and the word is
                # what travels - `landing` derives its tri-state from the
                # word so there is one representation of the fact.
                lane_mtime_state=lane_mtime_leg(
                    out["lane_file_mtime"], event["when"],
                    closing["when"] if closing else None)[0])
            out["landing_tally"][row["landing"]["verdict"]] = (
                out["landing_tally"].get(row["landing"]["verdict"], 0) + 1)

        if row["verdict"] == REWORK:
            if row["minutes"] is None:
                out["minutes_unknown"] += 1
                out["unpriced"].append(row["brief"])
            else:
                minutes += row["minutes"]
        out["rows"].append(row)
        out["tally"][row["verdict"]] = out["tally"].get(row["verdict"], 0) + 1

        # Every rung for every entry, kept so `rung_clashes` can cross the
        # ladder against itself. Deduplicated on the entry's line, because
        # a brief dispatched twice reads the same entries twice and one
        # heading disagreeing with itself is one finding, not two.
        seen_lines = {item["line"] for item in out["entry_rungs"]}
        for entry in entries_for(found, task) if task else []:
            if entry["line"] in seen_lines:
                continue
            out["entry_rungs"].append({
                "line": entry["line"], "task": task, "text": entry["text"],
                "brief": event["task"],
                "rungs": rung_readings(entry, task, event["when"], commits,
                                       lane=lane, known=known,
                                       branch_lanes=branch_lanes)})

    out["minutes"] = minutes
    return out


def _requeued(root, lane, filename):
    """Is this exact brief filename queued again. `True`, `False` or `None`.

    Looks in `queue/<lane>/` at depth 0 and in `queue/<lane>/RUNNING/`, and
    NOT in `DONE/` - a record in DONE is the opposite of re-queued. `None`
    where the folder cannot be listed, because a directory that cannot be
    read is not a directory with nothing in it.

    WHAT IT CANNOT ANSWER, and it is why `LANDING_AUTHORITIES` says so: a
    SUCCESSOR brief under a different number. `pilotcaps/0244` is the
    re-queue of `0241`'s work and shares not one character of its filename.
    Only a person reading the two briefs can pair them, so a False here means
    "not re-queued UNDER ITS OWN NUMBER" and never "nobody picked this up".
    """
    if not filename:
        return None
    base = os.path.join(root, "queue", lane)
    try:
        here = os.listdir(base)
    except OSError:
        # The AUTHORITY is this folder. Absent or unlistable, there is no
        # answer - not an answer of "not queued".
        return None
    if filename in here:
        return True
    running = os.path.join(base, "RUNNING")
    # A SUBFOLDER THAT IS NOT THERE CONTAINS NOTHING, which is different
    # from one that cannot be listed. Caught by C9d: `os.listdir` raises for
    # both, so the first version reported UNKNOWN for an estate whose base
    # folder it had just read successfully.
    if not os.path.isdir(running):
        return False
    try:
        return filename in os.listdir(running)
    except OSError:
        return None


def _candidate_shas(found):
    """Every hex token in every entry body. Filtered by git, not by guess."""
    shas = set()
    for item in found:
        shas.update(_SHA.findall(item["body"]))
    return shas


def _brief_mtime(root, lane, filename):
    """When the brief file was last written, or None.

    Read for ONE purpose: blind spot 2. `pilotcaps` 0233 and 0235 were
    rewritten keeping their filenames, so an entry predating the START can
    be about the brief's previous contents. A brief that has moved to
    `DONE/` is looked for there too, under the watcher's stamped name.
    """
    base = os.path.join(root, "queue", lane)
    for candidate in (os.path.join(base, filename),
                      os.path.join(base, "RUNNING", filename)):
        try:
            if os.path.exists(candidate):
                return datetime.datetime.fromtimestamp(
                    os.path.getmtime(candidate))
        except OSError:
            return None
    done = os.path.join(base, "DONE")
    try:
        names = os.listdir(done)
    except OSError:
        return None
    newest = None
    for name in names:
        if not name.endswith(filename):
            continue
        try:
            when = datetime.datetime.fromtimestamp(
                os.path.getmtime(os.path.join(done, name)))
        except OSError:
            continue
        if newest is None or when > newest:
            newest = when
    return newest


def rework(root=None, lanes_wanted=None, commits=None, now=None, cwd=None,
           branch_lanes=None, include_reflog=False):
    """The estate panel: one row per lane, then one total.

    THE TOTAL DOES NOT SUM OVER UNREADABLE LANES. A lane with no authority
    contributes to `lanes_unknown` and to nothing else, so the estate's
    denominator is the number of starts actually read and the panel says how
    many lanes are missing from it.
    """
    root = root or lanes.ops_root()
    out = {"state": None, "root_name": None, "variable": lanes.OPS_DIR,
           "lanes": [], "starts": 0, "rework": 0, "unknown": 0,
           "not_rework": 0, "minutes": 0.0, "minutes_unknown": 0,
           "lanes_unknown": 0, "lane_count": 0, "rewritten": 0,
           "offset_hours": None, "killed": 0, "landing_tally": {}}
    if not root:
        out["state"] = lanes.UNCONFIGURED
        return out
    out["root_name"] = os.path.basename(root.rstrip("\\/"))
    if not os.path.isdir(root):
        out["state"] = lanes.ABSENT
        return out
    out["state"] = lanes.PRESENT

    when = now or datetime.datetime.now()
    offset = lanes.local_utc_offset_hours(when)
    out["offset_hours"] = offset

    names = lanes_wanted
    if names is None:
        # `lane_names` answers `(name, where)` - where the lane was found,
        # which this panel does not use. A lane known only from a LANE file
        # and one known only from a queue folder are both read, because a
        # START line can only come from the log and the log is keyed on the
        # name whichever folder named it.
        names = [name for name, _where in lanes.lane_names(root)]
    out["lane_count"] = len(names)

    # The lane list is what makes the commit rung able to refuse. It is
    # DERIVED from the estate rather than a constant here, because a lane
    # added tomorrow would otherwise be invisible to the refusal and its
    # commits would start convicting its neighbours.
    for lane in names:
        row = lane_rework(root, lane, commits=commits, offset_hours=offset,
                          cwd=cwd, known=names, branch_lanes=branch_lanes,
                          include_reflog=include_reflog)
        out["lanes"].append(row)
        if row["state"] == UNREADABLE:
            out["lanes_unknown"] += 1
            continue
        out["starts"] += row["starts"] or 0
        out["minutes"] += row["minutes"] or 0.0
        out["minutes_unknown"] += row["minutes_unknown"]
        for verdict, count in row["tally"].items():
            if verdict == REWORK:
                out["rework"] += count
            elif verdict in UNKNOWN_VERDICTS:
                out["unknown"] += count
            elif verdict in NOT_REWORK:
                out["not_rework"] += count
        out["rewritten"] += sum(1 for item in row["rows"]
                                if item["rewritten"])
        for verdict, count in row["landing_tally"].items():
            out["landing_tally"][verdict] = (
                out["landing_tally"].get(verdict, 0) + count)
            out["killed"] += count
    return out


def killed_dispatches(data):
    """Every dispatch whose wrapper was killed, with its landing verdict.

    A SEPARATE LIST AND NOT MORE COLUMNS ON THE REWORK TABLE, because it is
    a different question: that table asks whether a dispatch repeated
    finished work, this one asks whether a dispatch's own work survived. A
    row can be both - `glm-c/0161` was a re-dispatch of an already-recorded
    brief AND was killed - and folding them would make either verdict read
    as the other.

    Sorted LANDED last, so the rows needing a person are at the top.
    """
    order = {NOT_DETERMINED: 0, LOST: 1, LANDED: 2}
    rows = []
    for lane in data.get("lanes", []):
        for item in lane.get("rows", []):
            if not item.get("landing"):
                continue
            rows.append({"lane": lane["lane"], "brief": item["brief"],
                         "task": item["task"], "at": item["at"],
                         "done": item["done"],
                         "suffix": item["done_suffix"],
                         "minutes": item["minutes"],
                         "landing": item["landing"]})
    rows.sort(key=lambda row: (order.get(row["landing"]["verdict"], 0),
                               row["at"] or ""))
    return rows


def landing_state(lane):
    """One lane's worst landing verdict, or None if it had no killed
    dispatch.

    WORST, NOT MOST COMMON. A lane with nine LANDED rows and one
    NOT-DETERMINED is a lane with an unanswered question in it, and a
    majority rule would render it healthy. This is `0170`'s rule applied one
    level up: an UNKNOWN that throws the alarm away is worse than a zero
    that keeps it.
    """
    tally = lane.get("landing_tally") or {}
    for verdict in (NOT_DETERMINED, LOST, LANDED):
        if tally.get(verdict):
            return verdict
    return None


# ---------------------------------------------------- pricing the blind spots


def commit_only(data, commits, known=(), branch_lanes=None):
    """The NO_ENTRY cohort, priced against git instead of the lane file.

    Blind spot 1, measured. `glm/0060` committed six mutation-proven tests
    and wrote no lane entry, so the lane-file authority reads NO_ENTRY for
    it and the headline calls it a first run. Git can answer the brief's
    actual question - had the work landed - for exactly this cohort, and the
    answer is reported HERE and never added to the headline, because it is a
    different authority and mixing two authorities for one number is how
    they drift.

    THE SAME LANE REFUSAL APPLIES, and the first version of this function
    did not have it: `97fec582d` is "TASK 0170 (GLM-C)" and it was reported
    as evidence that `glm-b/0170` and `qwen/0170` had already landed. Here
    the refusal has to be HARDER than in the commit rung, because there is
    no entry quoting the SHA to corroborate it - so a positive attribution
    is REQUIRED rather than merely not contradicted.
    """
    out = []
    for lane in data.get("lanes", []):
        name = lane["lane"]
        for row in lane["rows"]:
            if row["verdict"] != NO_ENTRY or not row["task"]:
                continue
            landed = None
            for sha, info in commits.items():
                named = [normalise_id(m.group(1))
                         for m in _HEAD_TASK.finditer(info["subject"])]
                if row["task"] not in named:
                    continue
                if info["when"] >= row["start"]:
                    continue
                if lane_tokens(info["subject"], name, known):
                    continue
                attribution = None
                if name in lane_tokens(info["subject"], None, known):
                    attribution = A_SUBJECT
                elif branch_lanes is not None:
                    seen = branch_lanes.get(sha)
                    if seen is not None and set(seen) == {name}:
                        attribution = A_BRANCHES
                if attribution is None:
                    # No entry, and nothing positively ties the commit to
                    # this lane. Reported as UNATTRIBUTED rather than as
                    # evidence, because a task number is not a lane.
                    attribution = A_UNCONTRADICTED
                if landed is None or info["when"] < landed["when"]:
                    landed = {"sha": sha, "when": info["when"],
                              "subject": info["subject"],
                              "attribution": attribution}
            if landed:
                out.append({"lane": name, "brief": row["brief"],
                            "start": row["start"], "sha": landed["sha"],
                            "when": landed["when"],
                            "attribution": landed["attribution"],
                            "subject": landed["subject"]})
    return out


def rung_clashes(data):
    """Entries where two rungs of the ladder place THE SAME entry differently.

    Within one entry, not across entries. Two entries for one id placed one
    before and one after a START is the ordinary two-run shape and is the
    signal rather than a defect - `both_runs_recorded` reports that. A
    single entry whose heading says one thing and whose own commit says
    another is a hand-typed date that is wrong, and this estate has been
    bitten by that often enough to print it.

    `D_SINGLE` is excluded because it is deliberately one-directional: it
    answers AT_OR_AFTER for everything it cannot convict, which would
    disagree with a correct `D_RANGE` by design.
    """
    out = []
    for lane in data.get("lanes", []):
        for item in lane.get("entry_rungs", []):
            readings = {field: reading
                        for field, reading in item["rungs"].items()
                        if field != D_SINGLE
                        and reading["position"] != UNDATABLE}
            seen = {reading["position"] for reading in readings.values()}
            if len(seen) > 1:
                out.append({"lane": lane["lane"], "brief": item["brief"],
                            "task": item["task"], "line": item["line"],
                            "text": item["text"],
                            "rungs": {field: (reading["position"],
                                              reading["value"])
                                      for field, reading
                                      in readings.items()}})
    return out


def both_runs_recorded(data):
    """Confirmed re-dispatches whose lane file holds BOTH runs' entries.

    The strongest shape in the corpus and worth naming separately: one entry
    dated before the START and another dated after it means the lane wrote
    the work up, the watcher dispatched it again, and the second session
    wrote it up a second time. Nothing has to be inferred about which run an
    entry belongs to.
    """
    out = []
    for lane in data.get("lanes", []):
        for row in lane["rows"]:
            if row["verdict"] != REWORK:
                continue
            seen = {item["position"] for item in row["placements"]}
            if BEFORE in seen and AT_OR_AFTER in seen:
                out.append({"lane": lane["lane"], "brief": row["brief"],
                            "placements": row["placements"]})
    return out


def blind_spots(data):
    """The three things this instrument cannot see, each with its size.

    Printed with the panel rather than filed in a docstring, because a limit
    nobody reads is a limit nobody applies.
    """
    rewritten = data.get("rewritten", 0)
    no_entry = 0
    for lane in data.get("lanes", []):
        no_entry += sum(1 for row in lane["rows"]
                        if row["verdict"] == NO_ENTRY)
    return [
        {"name": "work that landed with no lane entry",
         "size": no_entry,
         "denominator": data.get("starts", 0),
         "note": ("STARTs the lane file names in no entry heading. Each "
                  "reads as a first run, and glm/0060 proves a run can "
                  "commit its work and write no entry. Priced separately "
                  "by commit_only().")},
        {"name": "a brief rewritten under its own number",
         "size": rewritten,
         "denominator": data.get("rework", 0),
         "note": ("confirmed re-dispatches whose brief file is NEWER than "
                  "the entry that convicts them. pilotcaps 0233 and 0235 "
                  "were rewritten keeping their filenames on purpose, so "
                  "id equality is not task equality.")},
        {"name": "task prose shaped like a watcher record",
         "size": None,
         "denominator": data.get("starts", 0),
         "note": ("UNKNOWN and not measurable from the format. The watcher "
                  "appends each task's stdout into its own log, so a line "
                  "carrying the full `[stamp] [lane] START x` prefix would "
                  "be indistinguishable from a record. Nothing in this "
                  "corpus is, which is not a proof.")},
    ]


def describe(data=None):
    """One line per figure: what it is, and what it is not."""
    return {
        "verdicts": {name: VERDICT_TEXT[name] for name in VERDICT_ORDER},
        "ladder": [(name, FIELD_TEXT[name]) for name in LADDER],
        "authority": ("logs/watcher-<lane>.log for the START lines and "
                      "LANE-<lane>.md for the entries. Both are prose the "
                      "watcher and the lane sessions share; neither is a "
                      "ledger."),
        "not": ("NOT a count of finished work, NOT a count of DONE files - "
                "a DONE folder overstates finished work by 44% in this "
                "estate - and NOT a measure of whether a brief was "
                "worthwhile. It counts dispatches of work the lane file "
                "already recorded."),
        "minutes": ("the elapsed watcher time of the confirmed "
                    "re-dispatches only, START to its own DONE. A confirmed "
                    "re-dispatch with no DONE is counted in "
                    "minutes_unknown and contributes ZERO minutes, which "
                    "makes the cost figure a floor."),
        "data": data,
    }
