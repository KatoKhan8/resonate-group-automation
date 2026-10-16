#!/usr/bin/env python3
"""A figure two named authorities give differently is CONTESTED, never a number.

WHY THIS MODULE EXISTS, and it is three measured corrections rather than an
idea. This lane produced all three in two sessions and left every one of them
sitting beside the figure it contradicts:

    "101 unpushed"        101 branches fail the NAME check; 38 hold a commit
                          no remote ref can reach. 63 are durable under
                          another name. The old figure errs safe, and 63 false
                          alarms in a 101-row list is how a real list stops
                          being read.
    local `master`        `_STANDING-RULES.md` says "unpushed" and "nobody has
                          explained the local divergence". `rev-list
                          --left-right` answered `0 1`: it IS the merge base,
                          one commit BEHIND `origin/master`, and it is on the
                          remote verbatim as `main-local-master-2026-10-15`.
    the clone's size      the operator's log says the excluded worktree "now
                          holds 64 files". 64 is exactly its TOP-LEVEL count;
                          it holds 2,681. The prune is right and the count is
                          wrong by a factor of 42.

The estate's standing prohibition is that no number is repeated without its
denominator and its conditions. A page that prints ONE of two disagreeing
figures breaks that silently - which is worse than printing neither, because
the reader cannot tell a settled number from a contested one.

WHAT THIS DOES NOT DO, AND IT IS THE WHOLE DESIGN.

**IT DOES NOT RESOLVE A CONTEST.** Not by preferring the newer measurement,
not by majority, not by preferring the longer explanation, not by preferring
this lane's own reading. Nothing here sorts on a stamp. `0240`'s own section 9
was falsified by a reading taken SIXTY MINUTES EARLIER, so newer is not
righter, and a page that quietly picked the recent one would have picked the
wrong one in this estate's own history.

**IT TYPES NO VALUE AND NO AUTHORITY STRING.** Every value is extracted from
the file and the line the claim cites, and a citation that does not hold what
it claims is a VISIBLE FAILURE rather than a blank cell: BROKEN when the text
is nowhere in the file, DRIFTED when it is in the file at a different line -
which it will be, because these documents are appended to and every line
number in a citation is a decaying reference. `suppression/0210` is the
citation in this estate that was typed; nothing here can be.

**IT PERFORMS NO ARITHMETIC ON A CONTESTED FIGURE.** `total` refuses, names
the row that blocked it, and returns no number at all. A sum that silently
picked one side would launder a contest into a settled figure one layer down,
which is how a corrected number comes back.

**IT EDITS NOTHING.** `_STANDING-RULES.md` outranks every brief,
`CONTINUITY.md` and `CONTINUITY-LOG-*` are maintained by a scheduled run under
an mtime guard, and the `DECISIONS-*` documents are the operator's. This
module opens them read-only and `recommendations()` returns the exact line and
the one-sentence change for a person to apply.
"""
import os
import re

from src import lanes

# --------------------------------------------------------- what a claim is in
#
# FOUR STATES FOR A CITATION AND THREE OF THEM ARE NOT AN ANSWER. A claim
# whose own citation cannot be verified contributes NO value - it does not
# contribute a zero, an empty string or a guess, and it cannot make a figure
# agree with itself.

#: The file opened, the cited line exists, and the cited pattern matched THERE.
READ = "read"

#: The pattern is in the file, at a DIFFERENT line. The value is taken and the
#: real line is published beside the cited one, because the document grew and
#: a line number is a decaying reference - not because anybody was careless.
DRIFTED = "drifted"

#: The file opened and the pattern is nowhere in it. NO value is taken.
BROKEN = "broken"

#: The file could not be opened at all. NO value is taken.
UNREADABLE = "unreadable"

CITATION_TEXT = {
    READ: ("CITED CORRECTLY",
           "the file opened, the line the claim names exists, and the text "
           "the claim quotes is on that line. The value was taken from those "
           "bytes"),
    DRIFTED: ("LINE DRIFTED",
              "the quoted text IS in the file but not at the line cited. "
              "These documents are appended to, so a line number in a "
              "citation decays; the value is taken from where the text "
              "actually is and BOTH line numbers are shown"),
    BROKEN: ("CITATION BROKEN",
             "the file opened and the quoted text is nowhere in it. NO value "
             "is taken from this claim - a broken citation contributes "
             "nothing and must never render as a blank cell beside a number"),
    UNREADABLE: ("AUTHORITY UNREADABLE",
                 "the file named by this claim could not be opened. NO value "
                 "is taken. The path is printed so the failure is actionable "
                 "rather than invisible"),
}


# -------------------------------------------------------- what a figure is in

#: Two or more authorities were read and they do not agree. THE POINT OF THE
#: MODULE. Blocks arithmetic.
CONTESTED = "contested"

#: Two or more authorities were read and every one gives the same value.
AGREED = "agreed"

#: Exactly one authority was read. It renders as itself and is flagged
#: UNCONFIRMED - one authority is one authority, and a single reading must
#: never be promoted to agreement by there being nothing to disagree with it.
SINGLE = "single"

#: No authority could be read. UNKNOWN, which is not zero and not agreement.
#: Blocks arithmetic.
UNKNOWN = "unknown"

FIGURE_TEXT = {
    CONTESTED: ("CONTESTED",
                "two or more named authorities give this figure differently. "
                "BOTH values are shown with their own denominator and "
                "condition, and NOTHING here picks between them - not by "
                "recency, not by majority. Which reading is right is a "
                "measurement somebody has to take; no arithmetic on this "
                "page uses a contested figure"),
    AGREED: ("AGREED",
             "two or more named authorities were read and every one gives "
             "the same value. The count of authorities READ is shown over "
             "the count CITED, because agreement among two of four is not "
             "agreement among four"),
    SINGLE: ("ONE AUTHORITY - UNCONFIRMED",
             "exactly one named authority could be read. The value stands as "
             "itself and is NOT agreement: nothing has corroborated it, and "
             "a figure with nothing to disagree with it is unconfirmed rather "
             "than settled"),
    UNKNOWN: ("UNKNOWN",
              "no named authority could be read, so this page has no value "
              "for this question. UNKNOWN is not zero, not agreement and not "
              "safe, and no arithmetic uses it"),
}

#: Verdicts that make a figure unusable in any computed total. CONTESTED
#: because picking a side is the defect; UNKNOWN because invariant 0.
BLOCKING = (CONTESTED, UNKNOWN)


# ----------------------------------------------- what a RECOMMENDATION is in
#
# A SECOND STATE MACHINE, AND IT IS NOT THE CITATION ONE. Found 2026-10-16
# 21:50 by re-reading this page's own output at HEAD: between `0280` landing
# and that minute, the scheduled run applied the `local_master`
# recommendation to BOTH its places, and the page went on offering the edit
# with its quote marked `CITATION BROKEN`. Which is the SAFE direction - a
# broken quote takes no value and names no line - but it tells the reader
# this page's citation failed when what actually happened is that the
# document was fixed. On a page whose whole purpose is that a reader can tell
# a settled number from a contested one, "my citation broke" and "you have
# already done this" must not be the same cell.
#
# THE TWO SEARCHES ARE SEPARATE AND THAT IS THE WHOLE MECHANISM. The quote
# locates the line to edit. The `defect` pattern is the text the change
# exists to REMOVE, searched for independently across the whole file. Absence
# of the quote is never read as absence of the defect - that inference is how
# a page would congratulate itself for a change nobody made.

#: The quoted text is still in the file. The recommendation applies, at the
#: line the quote was actually found on. The defect pattern is not consulted
#: at all here: present text outranks any argument about it.
STANDS = "stands"

#: The quote is gone AND the defect text is nowhere in the file either. The
#: change appears to have been made by somebody else. NO edit is named, and
#: this is never stated as a fact - this page did not watch it change, so it
#: publishes what it searched for and asks for a verification.
SATISFIED = "satisfied"

#: The quote is gone and the defect text IS still there. The recommendation
#: STANDS and this page can no longer name the line. The louder state, and
#: the fail-closed direction: a document that quotes the defective wording in
#: order to correct it lands here rather than in SATISFIED.
RELOCATE = "relocate"

#: The file could not be read, or the entry names no defect pattern to search
#: for. NEVER satisfied. An absent pattern is a refusal, not a pass.
UNDETERMINED = "undetermined"

RECOMMENDATION_TEXT = {
    STANDS: ("RECOMMENDATION STANDS",
             "the text this recommendation quotes is still in the document, "
             "so the change has not been made and the line to change is "
             "named"),
    SATISFIED: ("APPEARS SATISFIED - VERIFY",
                "the quoted text is gone AND the wording this change exists "
                "to remove is nowhere in the document, so somebody appears "
                "to have made it. This page did NOT watch that happen: it "
                "names what it searched for and recommends no edit"),
    RELOCATE: ("STANDS - LINE LOST, DEFECT STILL PRESENT",
               "the quoted text is gone but the wording this change exists "
               "to remove is still in the document. The change is still "
               "needed and this page can no longer say on which line"),
    UNDETERMINED: ("UNDETERMINED - NOT SATISFIED",
                   "the document could not be read, or this entry names no "
                   "wording to search for. Nothing is concluded and this is "
                   "never reported as the change having been made"),
}


# --------------------------------------------------------------- the registry
#
# ONE ENTRY PER QUESTION, AND EVERY ENTRY IS CITATIONS RATHER THAN VALUES.
# There is no number anywhere in this registry that the renderer will print -
# the `pattern` is what the claim says it will find, and the value comes out
# of the file. A figure whose claims all stop matching renders UNKNOWN and
# names the paths, which is what this table is for.
#
# Paths are RELATIVE to the lane estate root, so nothing here holds somebody's
# home directory.

FIGURES = (
    {
        "key": "unreachable_branches",
        "question": "How many local branches hold work no remote ref can "
                    "reach?",
        "why_it_matters": "it is the durability alarm. 63 false rows in a "
                          "101-row list is how a real list stops being read, "
                          "and the gap is not an error in either measurement "
                          "- they answer different questions",
        "claims": (
            {
                "label": "the NAME check, METRIC A",
                "path": "TASK-0235/two-metrics.txt",
                "line": 9,
                "pattern": r"METRIC A TOTAL \(A fails\)\s*:\s*(?P<value>\d+)",
                "quote": "METRIC A TOTAL",
                "denominator": "581 local branch names against 518 remote "
                               "names",
                "condition": "a branch whose NAME is absent from the remote, "
                             "or present there with a different sha",
                "stamp": r"read at\s*:\s*(?P<stamp>\S+)",
            },
            {
                "label": "the same name check, re-run at close",
                "path": "TASK-0235/unpushed-0235.txt",
                "line": 22,
                "pattern": r"UNPUSHED TOTAL \(at-close\)\s*:\s*"
                           r"(?P<value>\d+)",
                "quote": "UNPUSHED TOTAL",
                "denominator": "every local branch not matching the remote",
                "condition": "the NAME check again, after one branch had "
                             "been pushed during the session",
                "stamp": r"read (?P<stamp>2026-\d{2}-\d{2} \d{2}:\d\w)",
            },
            {
                "label": "REACHABILITY, METRIC B",
                "path": "TASK-0235/two-metrics.txt",
                "line": 12,
                "pattern": r"NO remote ref can reach\s*:\s*(?P<value>\d+)",
                "quote": "NO remote ref can reach",
                "denominator": "the same 581 local branch names",
                "condition": "a branch holding a commit NO remote ref "
                             "reaches - the question durability actually asks",
                "stamp": r"read at\s*:\s*(?P<stamp>\S+)",
            },
        ),
    },
    {
        "key": "local_master",
        "question": "Where does the main checkout's local `master` stand "
                    "against `origin/master`?",
        "why_it_matters": "three standing documents call it diverged and "
                          "unexplained. If it is one commit BEHIND and "
                          "already on the remote under another name, then "
                          "nothing is at risk and three documents are "
                          "wrong - and it is one `rev-list` away either way",
        "claims": (
            {
                "label": "the standing rules",
                "path": "queue/_STANDING-RULES.md",
                "line": 28,
                "pattern": r"moved 00:13 today, (?P<value>\w+)",
                "quote": "moved 00:13 today",
                "denominator": "one ref against one ref",
                "condition": "stated, with no measurement quoted beside it",
                "stamp": r"Correction, (?P<stamp>\d{4}-\d{2}-\d{2} "
                         r"\d{2}:\d{2})",
            },
            {
                "label": "the object walk",
                "path": "TASK-0235/local-master-reachability.log",
                "line": 7,
                "pattern": r"local master is (?P<value>[A-Za-z/ ,]+)",
                "quote": "local master is",
                "denominator": "one ref against one ref, by "
                               "`merge-base --is-ancestor` and `rev-list "
                               "--left-right`",
                "condition": "measured against the objects rather than "
                             "against `status`",
                "stamp": r"(?P<stamp>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)",
            },
            {
                "label": "is it on the remote at all",
                "path": "TASK-0235/local-master-reachability.log",
                "line": 26,
                "pattern": r"(?P<value>refs/heads/main-local-master-\S+)",
                "quote": "refs/heads/main-local-master",
                "denominator": "one `ls-remote` read",
                "condition": "the same sha, found on the remote under a "
                             "different ref name",
                "stamp": r"(?P<stamp>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)",
            },
        ),
    },
    {
        # THE CONTROL ROW, AND IT IS NOT PADDING. An instrument that always
        # says CONTESTED sees nothing and reports it as caution, which is
        # B7's shape in the opposite direction from usual - so this page
        # carries one question two real authorities on this estate answer
        # the SAME way, measured from the same two files the row above
        # reads. Without it the three contests mean nothing.
        "key": "origin_master",
        "question": "What is `origin/master`?",
        "why_it_matters": "it is the one ref every lane reports against, "
                          "and the control on this whole page: if two "
                          "authorities agreeing cannot render as AGREED, "
                          "then CONTESTED is this instrument's only word "
                          "and it is measuring nothing",
        "claims": (
            {
                "label": "the standing rules",
                "path": "queue/_STANDING-RULES.md",
                "line": 26,
                "pattern": r"origin/master\s+(?P<value>[0-9a-f]{7,40})",
                "quote": "origin/master",
                "denominator": "one ref",
                "condition": "stated as the authority, abbreviated",
                "compare": "sha9",
                "stamp": r"Correction, (?P<stamp>\d{4}-\d{2}-\d{2} "
                         r"\d{2}:\d{2})",
            },
            {
                "label": "a live `ls-remote` read",
                "path": "TASK-0235/local-master-reachability.log",
                "line": 4,
                "pattern": r"origin/master, LIVE\s+=\s+"
                           r"(?P<value>[0-9a-f]{40})",
                "quote": "origin/master, LIVE",
                "denominator": "one ref",
                "condition": "read from the remote, in full",
                "compare": "sha9",
                "stamp": r"(?P<stamp>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)",
            },
        ),
    },
    {
        "key": "clone_files",
        "question": "How many files does the excluded clone under `logs\\` "
                    "hold?",
        "why_it_matters": "a conclusion was drawn from it - that the "
                          "worktree is gone - and the figure is the "
                          "top-level count rather than the tree's. The "
                          "exclusion it justifies is correct; the number is "
                          "wrong by a factor of 42",
        "claims": (
            {
                "label": "the operator's continuity log",
                "path": "CONTINUITY-LOG-2026-10-16.md",
                "line": 1365,
                "pattern": r"it now holds (?P<value>[\d,]+) files",
                "quote": "it now holds",
                "denominator": "a 687-file walk of `logs\\`",
                "condition": "the count `os.walk` reported for the pruned "
                             "directory, which is ONE directory level",
                "stamp": r"CLOSED `0360` exit0 (?P<stamp>\d{4}-\d{2}-\d{2} "
                         r"~\d{2}:\d{2})",
            },
            {
                "label": "the whole-tree walk",
                "path": "LANE-webapp.md",
                "line": 9173,
                "pattern": r"files anywhere under the clone\s+"
                           r"(?P<value>[\d,]+)",
                "quote": "files anywhere under the clone",
                "denominator": "every file under the clone, recursively",
                "condition": "`os.walk` without the prune, so the "
                             "subdirectories are visited",
                "stamp": r"## TASK-0240 . (?P<stamp>\d{4}-\d{2}-\d{2})",
            },
        ),
    },
)


# ----------------------------------------------------------------- the reader


#: The length a sha is compared at. Git's own abbreviation contract: an
#: abbreviated sha and its full form name ONE object, so comparing
#: `b1f290c84` against `b1f290c847eb...` as strings would report a contest
#: where there is none - the same error as calling `2,681` and `2681` two
#: values. Claims opt in with `"compare": "sha9"`; nothing infers it, because
#: a reader that guessed "this looks like a hash" would eventually truncate
#: something that is not one.
SHA_COMPARE_CHARS = 9


def _normalise(value, how=None):
    """What two values are compared BY. Never what is printed.

    Thousands separators and surrounding space are formatting, so `2,681` and
    `2681` are one value; case and inner spacing are NOT normalised away,
    because two documents using different words for one relation is exactly
    the disagreement this page exists to show.

    `how="sha9"` compares at git's abbreviation length. It can only ever
    MERGE two readings, never split them, so the risk it carries is a missed
    contest between two shas sharing nine characters rather than an invented
    one - and that is git's own contract for an abbreviation being usable.
    """
    if value is None:
        return None
    clean = value.replace(",", "").strip()
    if how == "sha9":
        return clean[:SHA_COMPARE_CHARS]
    return clean


def read_claim(root, claim):
    """One claim, verified against its own citation. Never a typed value.

    The path and the line come from the registry; the VALUE comes out of the
    file. Three of the four states return no value at all, and none of them
    returns an empty string - a blank beside a number is indistinguishable
    from a measurement of nothing.
    """
    path = os.path.join(root, *claim["path"].split("/")) if root else None
    row = {
        "label": claim["label"],
        "path": claim["path"],
        "cited_line": claim["line"],
        "quote": claim["quote"],
        "denominator": claim["denominator"],
        "condition": claim["condition"],
        "state": UNREADABLE,
        "found_line": None,
        "value": None,
        "normalised": None,
        "line_text": None,
        "stamp": None,
        "lines_in_file": None,
    }
    # THE LABELS ARE SET ON EVERY RETURN PATH, and that is a repair rather
    # than tidiness. The two UNREADABLE returns below used to set only `why`
    # and leave `state_label` and `state_why` absent, so `contested()`'s
    # own citation-failure list raised `KeyError: 'state_why'` - the page
    # CRASHED on exactly the case C5 exists to render visibly, which is the
    # worst possible way for a fail-visible path to fail. Caught by
    # `test_a_wrong_path_is_a_named_failure_and_takes_no_value`.
    def refuse(why):
        row["why"] = why
        label, default = CITATION_TEXT[row["state"]]
        row["state_label"] = label
        row["state_why"] = why or default
        return row

    if path is None or not os.path.exists(path):
        return refuse("the file this claim names is not there, so no value "
                      "is taken from it")
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            text = handle.read()
    except OSError:
        return refuse("the file this claim names could not be opened, so no "
                      "value is taken from it")

    lines = text.splitlines()
    row["lines_in_file"] = len(lines)
    pattern = re.compile(claim["pattern"])

    # THE CITED LINE FIRST, because a citation that holds is worth more than
    # a search that finds the same text somewhere else: it is the difference
    # between a reference that is still true and one that happens to be
    # recoverable.
    index = claim["line"] - 1
    if 0 <= index < len(lines):
        match = pattern.search(lines[index])
        if match:
            row["state"] = READ
            row["found_line"] = claim["line"]
            row["value"] = match.group("value").strip()
            row["line_text"] = lines[index].strip()

    if row["state"] != READ:
        # DRIFT, and it is the expected case rather than the exceptional one:
        # every one of these documents is appended to while this page is
        # being read.
        for number, line in enumerate(lines, start=1):
            match = pattern.search(line)
            if match:
                row["state"] = DRIFTED
                row["found_line"] = number
                row["value"] = match.group("value").strip()
                row["line_text"] = line.strip()
                break

    if row["state"] in (READ, DRIFTED):
        row["normalised"] = _normalise(row["value"], claim.get("compare"))
        row["compare"] = claim.get("compare")
        stamp = re.search(claim["stamp"], text) if claim.get("stamp") else None
        row["stamp"] = stamp.group("stamp") if stamp else None
    else:
        row["state"] = BROKEN
        row["why"] = ("the text this claim quotes is nowhere in the file it "
                      "names, so no value is taken from it")

    label, why = CITATION_TEXT[row["state"]]
    row["state_label"] = label
    row["state_why"] = row.get("why") or why
    return row


def read_figure(root, figure):
    """One question, every claim read, and a verdict that resolves nothing."""
    claims = [read_claim(root, claim) for claim in figure["claims"]]
    answered = [claim for claim in claims
                if claim["state"] in (READ, DRIFTED)]
    values = {claim["normalised"] for claim in answered}

    if not answered:
        verdict = UNKNOWN
    elif len(answered) == 1:
        verdict = SINGLE
    elif len(values) > 1:
        verdict = CONTESTED
    else:
        verdict = AGREED

    label, why = FIGURE_TEXT[verdict]
    return {
        "key": figure["key"],
        "question": figure["question"],
        "why_it_matters": figure["why_it_matters"],
        "claims": claims,
        "verdict": verdict,
        "verdict_label": label,
        "verdict_why": why,
        # READ OVER CITED, always both. Agreement among two of four is not
        # agreement among four, and a bare "AGREED" hides which it was.
        "claims_cited": len(claims),
        "claims_read": len(answered),
        # Every distinct value, sorted for a stable render and NEVER ordered
        # by stamp - an order by recency is a preference by recency wearing
        # a different word.
        "values": sorted(v for v in values if v is not None),
        # The single value, and ONLY where there is exactly one. None for a
        # contested figure, so a downstream caller cannot read a number off
        # a row that has two.
        "value": (sorted(values)[0] if len(values) == 1 else None),
        "blocks_arithmetic": verdict in BLOCKING,
        # Citations that did not hold, named rather than counted.
        "broken": [claim["path"] + ":" + str(claim["cited_line"])
                   for claim in claims if claim["state"] == BROKEN],
        "unreadable": [claim["path"] for claim in claims
                       if claim["state"] == UNREADABLE],
        "drifted": [claim["path"] + ":" + str(claim["cited_line"])
                    + " -> " + str(claim["found_line"])
                    for claim in claims if claim["state"] == DRIFTED],
    }


def contested(root=None, figures=FIGURES):
    """Every registered figure, read. `root` defaults to the lane estate.

    UNCONFIGURED and ABSENT travel through as themselves rather than as an
    empty table: "nobody said where the estate is" must never render as
    "no figure is contested".
    """
    root = root or lanes.ops_root()
    if root is None:
        return {"state": lanes.UNCONFIGURED, "root": None,
                "variable": lanes.OPS_DIR, "figures": [],
                "contested": [], "unknown": [], "agreed": [], "single": [],
                "blocked": [], "citation_failures": []}
    if not os.path.isdir(root):
        return {"state": lanes.ABSENT, "root": root,
                "variable": lanes.OPS_DIR, "figures": [],
                "contested": [], "unknown": [], "agreed": [], "single": [],
                "blocked": [], "citation_failures": []}

    rows = [read_figure(root, figure) for figure in figures]
    return {
        "state": lanes.PRESENT,
        "root": root,
        "root_name": os.path.basename(root),
        "variable": lanes.OPS_DIR,
        "figures": rows,
        "contested": [row["key"] for row in rows
                      if row["verdict"] == CONTESTED],
        "agreed": [row["key"] for row in rows if row["verdict"] == AGREED],
        "single": [row["key"] for row in rows if row["verdict"] == SINGLE],
        "unknown": [row["key"] for row in rows if row["verdict"] == UNKNOWN],
        "blocked": [row["key"] for row in rows if row["blocks_arithmetic"]],
        # Every citation that did not hold, across every figure, so a reader
        # can see at a glance whether this page is reading what it claims.
        "citation_failures": [
            {"figure": row["key"], "path": claim["path"],
             "cited_line": claim["cited_line"], "state": claim["state"],
             "why": claim["state_why"]}
            for row in rows for claim in row["claims"]
            if claim["state"] in (BROKEN, UNREADABLE)],
        "citations_drifted": [
            {"figure": row["key"], "path": claim["path"],
             "cited_line": claim["cited_line"],
             "found_line": claim["found_line"]}
            for row in rows for claim in row["claims"]
            if claim["state"] == DRIFTED],
    }


# ------------------------------------------------------- downstream arithmetic


def total(data, keys):
    """A sum over figures, which REFUSES rather than picks a side.

    THE WHOLE POINT IS THE REFUSAL. A total that quietly took one value off a
    contested row would launder the contest into a settled figure one layer
    down, and the figure would then be repeated without the conditions that
    make it mean two different things. So this returns `None` and NAMES the
    rows that blocked it - which is `0170`'s rule applied to a sum: a zero
    that is a provable bound keeps the alarm, and an UNKNOWN that throws the
    alarm away is worse than either.

    A figure whose value is not a number is also a refusal, named separately:
    "BEHIND/contained, not ahead" is a perfectly good answer and is not an
    addend.
    """
    by_key = {row["key"]: row for row in data.get("figures", [])}
    missing = [key for key in keys if key not in by_key]
    blocked = [key for key in keys
               if key in by_key and by_key[key]["blocks_arithmetic"]]
    unconfirmed = [key for key in keys
                   if key in by_key and by_key[key]["verdict"] == SINGLE]
    not_numeric = []
    addends = []
    for key in keys:
        row = by_key.get(key)
        if row is None or row["blocks_arithmetic"]:
            continue
        try:
            addends.append(int(row["value"]))
        except (TypeError, ValueError):
            not_numeric.append(key)

    refusals = []
    if missing:
        refusals.append("no such figure on this page: " + ", ".join(missing))
    if blocked:
        refusals.append(
            "these figures are CONTESTED or UNKNOWN and no arithmetic on "
            "this page uses one: " + ", ".join(blocked))
    if not_numeric:
        refusals.append("these figures are not numbers: "
                        + ", ".join(not_numeric))

    return {
        "keys": list(keys),
        # None, and never a partial sum. A sum over the rows that happened to
        # be usable, printed without saying which those were, is the
        # confident number about a subset this estate has a rule against.
        "value": None if refusals else sum(addends),
        "computed": not refusals,
        "blocked_by": blocked,
        "missing": missing,
        "not_numeric": not_numeric,
        # Figures that DID contribute, flagged where they rest on one
        # authority: a total built on unconfirmed rows is computable and is
        # not corroborated.
        "unconfirmed": unconfirmed,
        "addends": len(addends),
        "why": ("; ".join(refusals) if refusals
                else "every figure in this sum was read from two or more "
                     "agreeing authorities"),
    }


# --------------------------------------------------------- what a person does
#
# THE RECOMMENDATION, AND IT IS NOT APPLIED BY ANYTHING HERE. Each one names
# the document, the line and the one-sentence change, and every one of these
# documents is either under an mtime guard, maintained by a scheduled run, or
# outranks every brief.

# -------------------------------- THE SHAPES A `defect` PATTERN CANNOT EXPRESS
#
# MEASURED AND PRICED RATHER THAN BUILT FOR. `0280` filed a gap: this
# registry has no `defect` shape for a change whose removal target is a whole
# PARAGRAPH rather than a phrase, so a recommendation to delete one would
# have to name a phrase inside it. `0300` measured it at `5cd8925d8` and the
# measurement cancelled the build.
#
#   paragraph-shaped removal targets   0 of 3 live entries
#   multi-line removal targets         1 of 3 - the continuity log entry's
#                                      SECOND clause, "drop the inference
#                                      that the worktree is gone", which
#                                      spans :1367-:1368 of that document
#
# No live entry asks for a whole markdown block to be removed, so a
# paragraph-shaped pattern would have zero callers, and zero callers is
# worse than one. NOTHING WAS ADDED HERE. What follows is the price, so the
# next entry written into this registry is priced before it is added.
#
# THE SEARCH IS LINE BY LINE - `pattern.search(line)` over
# `body.splitlines()` - so a removal target that crosses a line break is not
# merely unpatterned, it is UNPATTERNABLE: no flag, `(?s)` included, makes a
# regex match text the reader never presents to it. And it does not fail
# into the refusal this registry already has for a shape it cannot express.
# Measured on two fixture documents carrying the wording in one form each,
# so a match could only come from the form under test:
#
#   the wording on ONE line            RELOCATE       correct, and loud
#   the same wording wrapped over two  SATISFIED      WRONG GREEN
#   no pattern named at all            UNDETERMINED   correct refusal
#
# The shape produces this page's ONLY green cell over a document that still
# carries the prose, while an entry naming NO pattern refuses correctly.
# Expressing a target badly is worse here than not expressing it at all.
#
# AND IT IS REACHABLE FROM A LIVE ENTRY, measured on the real bytes of
# CONTINUITY-LOG-2026-10-16.md with each edit applied to a copy: an entry
# carries ONE pattern for a change that may have SEVERAL clauses, and
# satisfying the patterned clause licenses SATISFIED for all of them. Apply
# that row's figure correction by rewording the sentence and the row goes
# green with the worktree-is-gone inference still in the document. Applying
# it as the row literally words it does NOT, because `it now holds 64 files`
# survives inside the longer sentence as a substring - which is luck rather
# than a guard, and luck is not a reason to leave it.
#
# ONE COUPLING THIS CODE CANNOT SEE ABOUT ITSELF. The mechanism keeps the
# two searches apart correctly. Whether they can DISAGREE is a property of
# each ENTRY'S DATA: the quote needle is `now.split(",")[0]`, and for the
# continuity log entry that is `it now holds 64 files`, which is its
# `defect` pattern character for character over the same single file. For
# that entry the two searches are one search wearing two names, and
# RELOCATE - quote gone, defect present - is unreachable by construction.
# 1 of 3 entries. An entry that supplies the same string twice gets the
# independence invariant's wording without its protection, so a new entry
# is checked against this before it is trusted.
#
# WHAT A FUTURE ENTRY WOULD NEED, if either shape ever arrives: a target
# spanning lines needs the search run over the joined text with the line
# numbers carried alongside, and a change with several clauses needs a
# pattern PER CLAUSE with SATISFIED requiring every one of them empty.
# Neither is written, because neither has a caller. `webapp/0300`.

RECOMMENDATIONS = (
    {
        "figure": "local_master",
        "path": "queue/_STANDING-RULES.md",
        "line": 28,
        "now": "moved 00:13 today, unpushed",
        "change": "replace `unpushed` with `one commit behind origin/master "
                  "and on the remote as main-local-master-2026-10-15`, and "
                  "delete the sentence 'Nobody has yet explained the local "
                  "divergence' - the `0 1` on `rev-list --left-right` "
                  "explains it.",
        # The wording the change removes. Measured present at 21:50 on
        # 2026-10-16, on the 01:05:36 bytes, so this one still STANDS.
        "defect": r"Nobody has yet explained the local divergence",
        "places": 1,
        "owner": "the operator. This file outranks every brief and is not "
                 "edited by a lane.",
    },
    {
        "figure": "local_master",
        "path": "CONTINUITY.md",
        "line": 16,
        "now": "`master` is a different ref and diverged on 2026-10-15",
        "change": "replace `diverged on` with `is one commit behind "
                  "origin/master as of`. The same word needs the same change "
                  "in DECISIONS-OPEN-2026-10-16.md, so this one is TWO "
                  "places - and they are not the two places `0240` named.",
        # `diverged on`, NOT `diverg` - and the difference is a measurement
        # rather than taste. At 21:50 `CONTINUITY.md` still contains
        # "byte-divergent" at :408 and "divergence unexplained" at :856, the
        # second being this document QUOTING `_STANDING-RULES.md` in order to
        # say it is wrong. A loose pattern matches both and reports the
        # defect present - the safe direction, and still the wrong answer.
        # The assertion this change removes is `diverged on <date>`, and that
        # is absent from both documents.
        "defect": r"diverged on 2026",
        "also": ("DECISIONS-OPEN-2026-10-16.md",),
        "places": 2,
        "owner": "the scheduled run that maintains these two under an mtime "
                 "guard.",
    },
    {
        "figure": "clone_files",
        "path": "CONTINUITY-LOG-2026-10-16.md",
        "line": 1365,
        "now": "it now holds 64 files, not 2,502",
        "change": "replace `64 files` with `64 files in its top level and "
                  "2,681 in the tree`, and drop the inference that the "
                  "worktree is gone - it is present and its mtimes are "
                  "unchanged.",
        # ONE PLACE, AND THIS IS DELIBERATELY NOT 0240'S TWO-PLACE
        # CORRECTION. That one is about the 27/27 figure, at :1365 and
        # :1784-1785. The 64 occurs ONCE. Two different corrections that
        # share a line number, and conflating them would have this page
        # recommending an edit to a line that does not carry the figure.
        #
        # Measured present at 21:50 on the 21:14:34 bytes, and `2,681`
        # occurs NOWHERE in that document - so unlike the row above, this
        # change has NOT been made and the figure and its inference both
        # still stand at :1367.
        "defect": r"it now holds 64 files",
        "places": 1,
        "owner": "the scheduled run. Read-only here.",
    },
)


def recommendations(data=None):
    """The recommendations, with each `now` string CHECKED against the file.

    A recommendation quoting text that is no longer there is a recommendation
    somebody will apply to the wrong line, so the quote is verified the same
    way a claim is and the result is published beside it.

    AND A BROKEN QUOTE IS TWO DIFFERENT SITUATIONS, which is why `standing`
    exists beside `quote_state`. The quote says where to edit; the `defect`
    pattern says whether there is still anything to edit, and the two are
    searched for SEPARATELY. A quote that is still present short-circuits the
    question entirely - nothing argues a document out of its own bytes.
    """
    root = (data or {}).get("root") or lanes.ops_root()
    rows = []
    for entry in RECOMMENDATIONS:
        row = dict(entry, quote_state=UNREADABLE, quote_found_line=None,
                   defect_present=None, defect_lines=[], defect_in=[])
        text = None
        path = (os.path.join(root, *entry["path"].split("/"))
                if root else None)
        if path and os.path.exists(path):
            try:
                with open(path, encoding="utf-8", errors="replace") as handle:
                    text = handle.read()
            except OSError:
                text = None
        if text is not None:
            lines = text.splitlines()
            row["quote_state"] = BROKEN
            needle = entry["now"].split(",")[0]
            for number, line in enumerate(lines, start=1):
                if needle in line:
                    row["quote_found_line"] = number
                    row["quote_state"] = (
                        READ if number == entry["line"] else DRIFTED)
                    break

            # THE SECOND SEARCH, over the whole file and over every further
            # document this change also touches - because a two-place
            # recommendation is not satisfied by one of its places.
            if entry.get("defect"):
                pattern = re.compile(entry["defect"])
                found = []
                for name in (entry["path"],) + tuple(entry.get("also", ())):
                    other = (os.path.join(root, *name.split("/"))
                             if root else None)
                    if other is None or not os.path.exists(other):
                        # An unreadable second place cannot license
                        # SATISFIED, so the whole row goes UNDETERMINED.
                        found = None
                        break
                    try:
                        with open(other, encoding="utf-8",
                                  errors="replace") as handle:
                            body = handle.read()
                    except OSError:
                        found = None
                        break
                    hits = [number for number, line
                            in enumerate(body.splitlines(), start=1)
                            if pattern.search(line)]
                    if hits:
                        found.append((name, hits))
                if found is None:
                    row["defect_present"] = None
                else:
                    row["defect_present"] = bool(found)
                    row["defect_in"] = [name for name, _ in found]
                    row["defect_lines"] = [
                        "%s:%s" % (name, ", ".join(str(h) for h in hits))
                        for name, hits in found]

        # FAIL CLOSED, AND SATISFIED IS THE ONLY STATE WITH TWO CONDITIONS.
        if row["quote_state"] in (READ, DRIFTED):
            row["standing"] = STANDS
        elif row["quote_state"] == UNREADABLE or row["defect_present"] is None:
            row["standing"] = UNDETERMINED
        elif row["defect_present"]:
            row["standing"] = RELOCATE
        else:
            row["standing"] = SATISFIED

        row["searched_for"] = entry.get("defect")
        row["recommends_an_edit"] = row["standing"] != SATISFIED
        label, why = CITATION_TEXT[row["quote_state"]]
        row["quote_state_label"] = label
        row["quote_state_why"] = why
        label, why = RECOMMENDATION_TEXT[row["standing"]]
        row["standing_label"] = label
        row["standing_why"] = why
        rows.append(row)
    return rows


def describe(data=None):
    """The page as text, for a terminal. Same reader, same refusals."""
    data = data if data is not None else contested()
    if data["state"] == lanes.UNCONFIGURED:
        return ("UNCONFIGURED: set %s to the lane estate's directory. That "
                "is NOT 'no figure is contested'." % data["variable"])
    if data["state"] == lanes.ABSENT:
        return ("ABSENT: %s names %s, which is not a directory."
                % (data["variable"], data["root"]))
    out = ["CONTESTED FIGURES   estate=%s" % data["root_name"],
           "%d figure(s): %d contested, %d agreed, %d single-authority, "
           "%d unknown"
           % (len(data["figures"]), len(data["contested"]),
              len(data["agreed"]), len(data["single"]),
              len(data["unknown"]))]
    for row in data["figures"]:
        out.append("")
        out.append("  %s" % row["question"])
        out.append("      %s   (%d of %d authorities read)"
                   % (row["verdict_label"], row["claims_read"],
                      row["claims_cited"]))
        for claim in row["claims"]:
            out.append("      %-18s %-34s %s:%s%s"
                       % (claim["value"] if claim["value"] is not None
                          else "NO VALUE",
                          claim["label"], claim["path"],
                          claim["found_line"] or claim["cited_line"],
                          "" if claim["state"] == READ
                          else "  [%s]" % claim["state_label"]))
            out.append("          over %s; %s; measured %s"
                       % (claim["denominator"], claim["condition"],
                          claim["stamp"] or "NO STAMP IN THE SOURCE"))
        if row["blocks_arithmetic"]:
            out.append("      -> no arithmetic on this page uses this figure")
    if data["citation_failures"]:
        out.append("")
        out.append("  CITATIONS THAT DID NOT HOLD:")
        for item in data["citation_failures"]:
            out.append("      %s:%s  %s" % (item["path"], item["cited_line"],
                                            item["state"]))
    out.append("")
    out.append("  WHAT A PERSON WOULD CHANGE, and whether it is still needed:")
    for rec in recommendations(data):
        out.append("      %-32s %s" % (rec["path"], rec["standing_label"]))
        out.append("          quote %s; searched for %r"
                   % (rec["quote_state_label"],
                      rec["searched_for"] or "NOTHING NAMED"))
        if rec["defect_lines"]:
            out.append("          still present at %s"
                       % "; ".join(rec["defect_lines"]))
    return "\n".join(out)


if __name__ == "__main__":                                  # pragma: no cover
    print(describe())
