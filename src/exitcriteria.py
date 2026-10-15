#!/usr/bin/env python3
"""The nine CANARY-01 exit criteria, read from recorded artifacts.

WHY THIS MODULE EXISTS. `CANARY-01.md` lists nine exit criteria and says the
canary activates "only when all of these are true". So the one question that
gates a first live send to real people is: which of the nine are true, on what
evidence, measured when. Answering it has meant opening a 395 KB append-only
lane file and trusting the last table in it - and on 2026-10-15 four of the
nine were recorded NOT MET while the lane files simultaneously carried older
blocks saying something else.

THE DIRECTION THIS MODULE MAY NOT FAIL IN. A reader that says UNKNOWN when the
answer is MET costs somebody an afternoon. A reader that says MET when the
answer is unknown puts mail in front of prospects. Those are not symmetric, so
every refusal here leans the same way:

    an absent source               -> UNKNOWN, never MET
    a source that cannot be parsed -> UNKNOWN, never MET
    `MET-WITH-CAVEAT`              -> UNKNOWN, and the words shown verbatim
    two verdicts for one criterion -> UNKNOWN, named as contested
    a verdict phrase not known     -> UNKNOWN, and the words shown verbatim
    a self-control that FAILED     -> UNKNOWN on every row on the page

THE CONTROL THAT STOPS THAT BEING FREE, and it is this lane's own B7 finding
turned into code. A reader that answers UNKNOWN to everything satisfies all of
the above and is worthless: clean because it sees nothing. So `controls()` runs
three checks on EVERY render - an absent source renders UNKNOWN, an
unparseable one renders UNKNOWN, and a PLANTED set of verdicts comes back
exactly as planted, in both directions. If any of the three FAILS, every
verdict on the page becomes UNKNOWN, because a reader that cannot demonstrate
it works has no standing to report a pass.

WHAT IT DOES NOT DO. It does not measure a criterion. Not one verdict here is
derived: each is read out of an artifact somebody else recorded, and the row
says which artifact and how old it is. `as of` is the timestamp of the
ARTIFACT, never of the render - a stale verdict shown with its real age is
useful, and the same verdict shown as current is the one that gets believed.
It writes no file, opens no socket, reaches no provider and reads no
credential.

AND THE PART A READER MUST NOT MISS. Three of the nine have an authority this
process cannot read at all - criterion 7 needs a provider call nobody has
approved, criterion 8 is the operator's own reply, criterion 9 is a thing that
does not exist yet. `LOCATION_TEXT` says so per row rather than letting an
UNKNOWN look like a file that happens to be missing today. That is TASK 0020's
measurement applied: six of eleven operator questions have an authority
outside `src/web/`, and a page that implies otherwise is the defect.

    py -3 -m src.exitcriteria
"""
import datetime
import os
import re

from src import lanes

#: One estate, one variable. Reused from `src.lanes` rather than introduced,
#: because a second name for the same directory is how two readers come to
#: disagree about where the lanes are.
OPS_DIR = lanes.OPS_DIR

#: This repository's root, from this file's own location. Used for the
#: repository-sourced authority and for the absence control, and deliberately
#: NOT taken from a setting: a control pointed at a configurable path can be
#: pointed at a path that happens to exist.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---------------------------------------------------------------- verdicts

MET = "met"
NOT_MET = "not_met"
UNKNOWN = "unknown"

#: The three words this page can say, and what each one does NOT license.
#: The renderer takes its labels from here, so it cannot drift from the
#: reader, and a verdict the reader has not named arrives as None rather than
#: being filed into whichever bucket is first.
VERDICT_TEXT = {
    MET: ("MET",
          "a recorded artifact states this criterion is met. That is a "
          "reading of somebody else's measurement, not a measurement by "
          "this page, and it is only as good as the `as of` beside it"),
    NOT_MET: ("NOT MET",
              "a recorded artifact states this criterion is not met. "
              "CANARY-01 activates only when all nine are met, so one of "
              "these is sufficient to say the canary does not go"),
    UNKNOWN: ("UNKNOWN",
              "no artifact this page can read answers this criterion, or "
              "what it says is not one of the two verdicts above. UNKNOWN "
              "is NOT met, NOT not-met, and never safe: the criterion may "
              "be true and may be false, and nobody here knows which"),
}

# ----------------------------------------------------------- source states
#
# Each of these is a thing a reader must be able to tell apart from the
# others. Collapsing any pair of them is the defect this module exists for.

UNCONFIGURED = "unconfigured"   # nobody has said where the ops estate is
ABSENT = "absent"               # the path is not there
UNREADABLE = "unreadable"       # it is there and could not be read
EMPTY = "empty"                 # readable, and holds nothing
NO_BLOCK = "no_block"           # read in full, and holds no verdict block
PRESENT = "present"             # read, and a verdict block was found

# ------------------------------------------------------------- as-of kinds

AS_OF_STAMP = "stamp"   # a date in the document, above the block it belongs to
AS_OF_MTIME = "mtime"   # the file's modification time, because it named none
AS_OF_NONE = "none"     # neither: no age could be established at all

#: How old a verdict may be before the page marks it stale. Twenty-four hours
#: because this estate moves in hours - four lanes landed work against these
#: criteria in one evening - and because a verdict is invalidated by a commit
#: rather than by the clock, which nothing here can see. So `stale` is a
#: prompt to re-measure and is never a verdict: it does not change one.
STALE_SECONDS = 24 * 3600

# -------------------------------------------------------------- the nine
#
# The criteria themselves, their one-sentence form, and - the column that
# matters - the authority that answers each one and whether this process can
# reach it. Taken from `CANARY-01.md`'s own "Exit criteria" section. This
# module holds a copy because the definition file lives outside the
# repository, and a page that cannot enumerate the nine when that file is
# missing is a page that silently shrinks. `registry_drift` in the report is
# how that copy going stale becomes visible instead of invisible.

LOC_REPO = "repo"           # a tracked artifact in this repository
LOC_OPS = "ops"             # a file in the ops estate, outside the repository
LOC_OPERATOR = "operator"   # only the operator can answer it
LOC_PROVIDER = "provider"   # only a provider read answers, and none is approved

LOCATION_TEXT = {
    LOC_REPO: ("in this repository",
               "a test or an instrument on a branch. Reachable here in "
               "principle - but a proof on a branch this checkout does not "
               "contain is not reachable from this checkout, and on "
               "2026-10-15 no single tree held more than one of the nine"),
    LOC_OPS: ("in the ops estate, outside the repository",
              "a file beside the lane files. Not in git, so it cannot be "
              "reconstructed from a clone, and a fresh session on another "
              "machine cannot read it at all"),
    LOC_OPERATOR: ("with the operator",
                   "no artifact and no instrument can answer this. It is a "
                   "person reading copy and replying, and until he does it "
                   "is UNKNOWN however much code is written"),
    LOC_PROVIDER: ("behind a provider read nobody has approved",
                   "settled by one fully-walked provider call. The "
                   "2026-09-26 freeze stands and no such read is "
                   "authorised, so this is UNKNOWN by policy rather than "
                   "by accident - and offline evidence has already "
                   "disagreed with itself about it"),
}

CRITERIA = (
    {"number": 1,
     "statement": "A suppressed address cannot reach the transport by any "
                  "path, and a test goes RED when the suppression check is "
                  "removed.",
     "authority": "a RED-on-removal test over `src/suppression.py`, plus the "
                  "count of write paths with no suppression consult",
     "location": LOC_REPO},
    {"number": 2,
     "statement": "A reply asking for removal results in a written "
                  "suppression row, demonstrated rather than assumed.",
     "authority": "a test that reads the written row back after the reply "
                  "is processed",
     "location": LOC_REPO},
    {"number": 3,
     "statement": "`li1` renders a real connection note for every contact "
                  "in the cohort, and a test goes RED if it renders empty.",
     "authority": "`config/linkedin/productive-standard.json` and a test "
                  "that fails on an empty note",
     "location": LOC_REPO},
    {"number": 4,
     "statement": "Every template `stage_s7_copy` can render passes both the "
                  "word ceiling and the word floor, and a test goes RED if a "
                  "template escapes the check.",
     "authority": "the writer contract's bounds, applied to every "
                  "renderable template rather than to a hand-kept list",
     "location": LOC_REPO},
    {"number": 5,
     "statement": "The count of provider write paths that bypass the gate is "
                  "zero, stated as a fraction of the real denominator.",
     "authority": "an instrument that derives the denominator from the "
                  "providers' own call graphs, naming no filename by hand",
     "location": LOC_REPO},
    {"number": 6,
     "statement": "Mailbox health is established for the estate the canary "
                  "sends from.",
     "authority": "the full estate export, read offline with no provider "
                  "call",
     "location": LOC_OPS},
    {"number": 7,
     "statement": "Every sender email attached to the campaign has the same "
                  "owner, and every rendered body is signed with that "
                  "owner's name.",
     "authority": "one fully-walked `GET /sender-emails`, which returns id, "
                  "address and signature and settles it",
     "location": LOC_PROVIDER},
    {"number": 8,
     "statement": "The review file is approved by the owner.",
     "authority": "the operator's own `APPROVED <campaign> <file hash>` "
                  "reply against the hashed approval sheet",
     "location": LOC_OPERATOR},
    {"number": 9,
     "statement": "A kill switch the owner can operate alone is named and "
                  "tested.",
     "authority": "a named artifact the operator can operate without a "
                  "shell, and a test that proves it halts sending",
     "location": LOC_OPERATOR},
)

# ------------------------------------------------------------- the sources
#
# Where a recorded verdict is looked for, in order. The FIRST source holding
# a row for a criterion answers it, whatever that row says - a lower-ranked
# source is never allowed to resolve a higher one's UNKNOWN, because that
# would be this page choosing a verdict rather than reading one.

#: pilotcaps TASK 0210's re-audit. The designated authority, and as of this
#: module being written it does not exist yet - which is exactly the state
#: the page has to render honestly rather than fill in.
DESIGNATED = "EXIT-CRITERIA-2026-10-16.md"

#: pilotcaps TASK 0160's committed audit of the nine as a set. In the
#: repository, and on 2026-10-15 reachable from exactly one ref.
IN_REPO_AUDIT = "docs/CANARY-01-EXIT-CRITERIA-AUDIT-2026-10-15.md"

#: The lane's own report of that audit. Ranked last and labelled for what it
#: is, because a lane's claim about its own work is a claim.
LANE_REPORT = "LANE-pilotcaps.md"

#: `CANARY-01.md` itself - the authority for WHICH criteria exist, not for
#: whether any of them is met. Read only to check this module's copy of the
#: nine has not gone stale.
DEFINITION = "CANARY-01.md"

SOURCES = (
    {"key": DESIGNATED, "name": DESIGNATED, "rank": 1, "where": LOC_OPS,
     "kind": "the designated authority: pilotcaps TASK 0210's re-audit of "
             "the nine, each verdict measured at a named SHA"},
    {"key": IN_REPO_AUDIT, "name": IN_REPO_AUDIT, "rank": 2,
     "where": LOC_REPO,
     "kind": "pilotcaps TASK 0160's committed audit of the nine as a set. "
             "In git, so a clone can reconstruct it - if the clone holds "
             "the branch it was committed to"},
    {"key": LANE_REPORT, "name": LANE_REPORT, "rank": 3, "where": LOC_OPS,
     "kind": "a lane's own report of its audit, and NOT the audit itself. "
             "A lane's claim about its own work is a claim: 2026-10-15 "
             "produced four corrections to exactly that kind of claim"},
)

# -------------------------------------------------------------- the parser

#: A criterion number at the head of a line. Tolerates the indented block
#: shape TASK 0160 wrote and the markdown table shape TASK 0210's brief
#: describes, because the format is not known in advance.
#:
#: Single digit 1-9 only, and the character after it must be a separator.
#: That is what keeps `10 companies / 30 contacts` and `1,147 campaign-slot
#: claims` - both of which appear in these very documents - from being read
#: as criteria 1.
_NUMBER = re.compile(r"^[|\s]*`?([1-9])`?(?=[|.):]|\s)")

#: The verdict phrases, longest first. TWO SEPARATE THINGS PROTECT THE TWO
#: COLLISIONS HERE, and conflating them cost this comment one revision: a
#: mutation that reordered the alternation went red, but NOT through the test
#: that was supposed to catch it, which is how the claim below got corrected.
#:
#:   `NOT MET` is safe because the ALTERNATIVE EXISTS, not because of where
#:   it sits. Python scans left to right, so it reaches the `N` before the
#:   `MET` and matches the whole phrase from there whatever the order.
#:   DELETING `NOT[\s-]+MET` is what reads every refusal as a pass, and that
#:   is the mutation `test_not_met_is_never_read_as_met` actually kills.
#:
#:   `MET WITH CAVEAT` is safe because of the ORDER. `MET` is a PREFIX of it,
#:   and at that one position the alternation is leftmost-first, so a bare
#:   `MET` placed earlier matches three letters and the caveat is lost -
#:   measured, and it turns an UNKNOWN into a MET.
#:
#: A prefix collision and a substring collision are different failures and
#: one guard does not cover both, so each has its own mutation.
#:
#: UPPERCASE ONLY, deliberately. These documents say "is met" in prose on
#: nearly every page; a case-insensitive reader would harvest verdicts out of
#: sentences. A real verdict written in mixed case therefore yields no token,
#: which renders UNKNOWN with the words shown - safe and visible.
_TOKEN = re.compile(
    r"\b(?:NOT[\s-]+MET|MET[\s-]+WITH[\s-]+CAVEAT|UNKNOWN|MET)\b")

#: What each recorded phrase means here. `MET WITH CAVEAT` is the one that
#: matters: two of the nine were recorded that way, and it is not one of the
#: three verdicts this page can render. Rounding it up to MET is a guess in
#: the unsafe direction; rounding it down to NOT MET would be this page
#: inventing a verdict the authority did not write. So it is UNKNOWN, and the
#: recorded words travel with the row.
_MEANING = {
    "MET": MET,
    "NOT MET": NOT_MET,
    "UNKNOWN": UNKNOWN,
    "MET WITH CAVEAT": UNKNOWN,
}

#: How many of the nine a run of numbered lines must name - AND how many of
#: those lines must actually record a verdict - before it counts as a verdict
#: block. A majority on both counts.
#:
#: THE SECOND CONDITION WAS ADDED FROM A MEASUREMENT, not from caution. With
#: only the first, `LANE-pilotcaps.md` yielded eleven accepted blocks and the
#: LAST one was a numbered list of six open operator decisions, 272 lines
#: below the real verdict table. A roster of nine contacts with their word
#: counts qualified too. Both are runs of nine or six numbered lines carrying
#: no verdict word at all, and in an append-only file 6,000 lines long there
#: are many of them. Requiring a majority of the rows to carry a recognised
#: verdict phrase rejects both and accepts the real table - and it is
#: strictly stricter, so it cannot turn an UNKNOWN into a MET.
MIN_BLOCK = 5

#: How many lines that are neither a numbered row nor an indented
#: continuation may sit inside one block before it is closed.
MAX_GAP = 2

#: A date, for the `as of`. Only the ISO form is accepted; a reader that
#: guessed at `15 Oct` would be guessing the year.
#:
#: BOTH BOUNDARIES ARE EXPLICIT, AND NOT `\b`. A hyphen is a non-word
#: character, so `\b` matches happily inside `task-pilotcaps-enforcer-
#: 2026-10-14` - and that is not a hypothetical: the first read of the real
#: lane file dated TASK 0160's verdict block 2026-10-14 by harvesting the
#: date out of the BRANCH NAME two lines above it, when the entry's own
#: heading says 2026-10-15. A date glued into an identifier is a branch, a
#: filename or a worktree, and none of those is when a measurement was taken.
_DATE = re.compile(r"(?<![-\w])(\d{4}-\d{2}-\d{2})(?![-\w])")

#: A numbered list item in `CANARY-01.md`'s own criteria section. Two digits
#: allowed here - unlike `_NUMBER` - precisely so that a TENTH criterion is
#: counted and reported as drift rather than silently ignored.
_LIST_ITEM = re.compile(r"^\s*(\d{1,2})\.\s")


def number_on(line):
    """The criterion number this line is about, or None."""
    match = _NUMBER.match(line)
    return int(match.group(1)) if match else None


def _tokens_on(line):
    """Every verdict phrase on the line, verbatim and in order."""
    return [match.group(0) for match in _TOKEN.finditer(line)]


def _normalise(token):
    return re.sub(r"[\s-]+", " ", token).strip().upper()


def _indented(line):
    """Whether this line can be a continuation of the row above it.

    A continuation must be indented, or be a table row. Without that rule the
    paragraph after a table contributes a second verdict to its last row -
    and the prose under one of these tables routinely argues about a verdict.
    """
    return line[:1] in (" ", "\t") or line.lstrip().startswith("|")


def _decide(row):
    """One row's verdict from its recorded phrases. Fails closed, loudly."""
    verbatim = row["tokens"]
    if not verbatim:
        return UNKNOWN, None, (
            "the authority names this criterion and records no verdict this "
            "page can read. Its line is shown beside this; a verdict written "
            "in mixed case or in words is not read as a verdict rather than "
            "being guessed at")
    distinct = {_normalise(token) for token in verbatim}
    if len(distinct) > 1:
        return UNKNOWN, " / ".join(verbatim), (
            "CONTESTED: the authority records %d different verdicts for this "
            "one criterion - %s. That is not a verdict, and taking whichever "
            "came first would read MET off a row whose second answer is NOT "
            "MET" % (len(distinct), ", ".join(sorted(distinct))))
    only = distinct.pop()
    verdict = _MEANING.get(only)
    if verdict is None:
        return UNKNOWN, verbatim[0], (
            "the authority records %s, which is not a verdict this page can "
            "read" % verbatim[0])
    if verdict is UNKNOWN and only == "UNKNOWN":
        return UNKNOWN, verbatim[0], (
            "the authority itself recorded UNKNOWN. That is agreed with, not "
            "resolved: it names a measurement nobody has been able to make")
    if verdict is UNKNOWN:
        # The VERBATIM phrase, not the normalised one. A reader has to see
        # the words the authority actually wrote, or this page is quoting
        # its own paraphrase back as evidence.
        return UNKNOWN, verbatim[0], (
            "the authority records %s, which is not one of the three "
            "verdicts this page can render. It is NOT rounded up to MET - "
            "the caveat is the whole content of the answer - and it is not "
            "rounded down either, because this page does not write verdicts"
            % verbatim[0])
    return verdict, verbatim[0], None


def _is_verdict_block(block):
    """Whether a run of numbered lines is a verdict table or just a list.

    Both conditions are a majority of the nine, and the second one is the
    one that does the work in a real document: a numbered list of operator
    decisions, and a roster of nine contacts with their word counts, are
    both runs of numbered lines and neither records a verdict.
    """
    if len(block["rows"]) < MIN_BLOCK:
        return False
    carrying = len([row for row in block["rows"].values() if row["tokens"]])
    return carrying >= MIN_BLOCK


def verdicts_from_text(text):
    """Every verdict block in a document, and the last one's rows.

    The LAST accepted block wins, because these files are append-only and an
    earlier block is a superseded entry. The count of superseded blocks is
    reported rather than dropped, so a reader can see the document holds
    more than one answer.
    """
    lines = text.splitlines()
    blocks = []
    current = None
    gap = 0

    def close():
        nonlocal current, gap
        if current and _is_verdict_block(current):
            blocks.append(current)
        current = None
        gap = 0

    for index, raw in enumerate(lines):
        if raw.strip().startswith("#"):
            # A heading always ends a block. Two short runs either side of one
            # are two runs, never a single table that happens to span it.
            close()
            continue
        number = number_on(raw)
        tokens = _tokens_on(raw)
        if number is not None:
            if current is None:
                current = {"rows": {}, "order": [], "start": index}
            if number in current["rows"]:
                # The same criterion twice inside one block. Not collapsed:
                # the phrases accumulate, so two different answers come out
                # CONTESTED rather than last-one-wins.
                current["rows"][number]["tokens"].extend(tokens)
            else:
                current["rows"][number] = {
                    "number": number, "line": raw.rstrip(),
                    "tokens": list(tokens)}
                current["order"].append(number)
            gap = 0
        elif current is not None and tokens and _indented(raw):
            if current["order"]:
                current["rows"][current["order"][-1]]["tokens"].extend(tokens)
            gap = 0
        elif current is not None:
            gap += 1
            if gap > MAX_GAP:
                close()
    close()

    if not blocks:
        return {"blocks": 0, "superseded": 0, "rows": {}, "stamp": None}

    winner = blocks[-1]
    rows = {}
    for number, row in winner["rows"].items():
        verdict, recorded, reason = _decide(row)
        rows[number] = {"number": number, "verdict": verdict,
                        "recorded": recorded, "reason": reason,
                        "line": row["line"]}
    return {"blocks": len(blocks), "superseded": len(blocks) - 1,
            "rows": rows, "stamp": _stamp_above(lines, winner["start"])}


def _stamp_above(lines, start):
    """The nearest date at or above the block, which is its own `as of`.

    A lane file holds dozens of entries and the date in the heading above a
    block is that entry's date. Searching the whole document for the newest
    date would hand a 2026-10-15 block today's heading.
    """
    for index in range(start, -1, -1):
        match = _DATE.search(lines[index])
        if match:
            return match.group(1)
    return None


# --------------------------------------------------------------- the reading

def ops_root():
    """Where the ops estate is, and which kind of nothing when it is not.

    UNCONFIGURED and ABSENT are different answers and neither is "no
    verdicts": the first says nobody has pointed this page at the estate,
    the second says the path it was pointed at is not there.
    """
    raw = os.environ.get(OPS_DIR)
    if not raw or not raw.strip():
        return None, UNCONFIGURED
    root = raw.strip()
    if not os.path.isdir(root):
        return root, ABSENT
    return root, PRESENT


def read_source(path):
    """A source file's text, or the exact kind of nothing it is instead."""
    if not os.path.exists(path):
        return {"state": ABSENT, "text": None, "mtime": None}
    if not os.path.isfile(path):
        # A directory where a file belongs. Not absent and not empty - a
        # shape nobody planned for, which fails closed rather than crashing.
        return {"state": UNREADABLE, "text": None, "mtime": None}
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            text = handle.read()
        mtime = os.path.getmtime(path)
    except OSError:
        return {"state": UNREADABLE, "text": None, "mtime": None}
    if not text.strip():
        return {"state": EMPTY, "text": "", "mtime": mtime}
    return {"state": PRESENT, "text": text, "mtime": mtime}


def _as_of(stamp, mtime, now):
    """The artifact's own timestamp, its age, and which of the two it is.

    Never the render's clock. A stale verdict shown with its real age is
    useful; the same verdict shown as current is the one that gets believed,
    and that is the defect this page exists to avoid.
    """
    when = None
    kind = AS_OF_NONE
    label = None
    if stamp:
        try:
            when = datetime.datetime.strptime(stamp, "%Y-%m-%d")
            kind = AS_OF_STAMP
            label = stamp
        except ValueError:
            when = None
    if when is None and mtime is not None:
        when = datetime.datetime.fromtimestamp(mtime)
        kind = AS_OF_MTIME
        label = when.replace(microsecond=0).isoformat(" ")
    if when is None:
        return {"as_of": None, "as_of_kind": AS_OF_NONE, "age_seconds": None,
                "as_of_in_future": False, "stale": False}
    age = int((now - when).total_seconds())
    if age < 0:
        # A stamp ahead of the clock. Reported as its own condition rather
        # than as a negative age or a fresh verdict - one of the two is
        # wrong and this page cannot say which.
        return {"as_of": label, "as_of_kind": kind, "age_seconds": None,
                "as_of_in_future": True, "stale": False}
    return {"as_of": label, "as_of_kind": kind, "age_seconds": age,
            "as_of_in_future": False, "stale": age > STALE_SECONDS}


def _resolve(source, root, ops, ops_state):
    """A source's absolute path, or why there is none to read."""
    if source["where"] == LOC_OPS:
        if ops_state != PRESENT:
            return None, ops_state
        return os.path.join(ops, source["name"]), None
    return os.path.join(root, source["name"].replace("/", os.sep)), None


def _registry_check(root, ops, ops_state, now):
    """Whether `CANARY-01.md` still lists exactly the nine this module holds.

    The definition lives outside the repository, so this module carries a
    copy of the nine. A copy is a second representation of a truth, which is
    how two things drift - so the drift is measured rather than hoped away,
    and an unreadable definition is UNCHECKED rather than agreement.
    """
    del root, now
    if ops_state != PRESENT:
        return {"registry_state": ops_state, "registry_drift": None,
                "registry_unchecked": True, "registry_count": None,
                "registry_file": DEFINITION}
    source = read_source(os.path.join(ops, DEFINITION))
    if source["state"] != PRESENT:
        return {"registry_state": source["state"], "registry_drift": None,
                "registry_unchecked": True, "registry_count": None,
                "registry_file": DEFINITION}
    numbers = set()
    inside = False
    for line in source["text"].splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            inside = "exit criteria" in stripped.lower()
            continue
        if not inside:
            continue
        match = _LIST_ITEM.match(line)
        if match:
            numbers.add(int(match.group(1)))
    if not numbers:
        return {"registry_state": NO_BLOCK, "registry_drift": None,
                "registry_unchecked": True, "registry_count": 0,
                "registry_file": DEFINITION}
    drift = None
    if numbers != {criterion["number"] for criterion in CRITERIA}:
        drift = ("%s lists criteria %s, and this page holds %d. The page's "
                 "copy of the criteria has gone stale, so the rows below may "
                 "be an incomplete set - which is worse than a wrong verdict, "
                 "because a missing row looks like nothing at all"
                 % (DEFINITION, ", ".join(str(n) for n in sorted(numbers)),
                    len(CRITERIA)))
    return {"registry_state": PRESENT, "registry_drift": drift,
            "registry_unchecked": False, "registry_count": len(numbers),
            "registry_file": DEFINITION}


def _read_chain(sources, root, ops, ops_state, now):
    """Every source, read and parsed, in rank order. One pass, no fallbacks.

    A source carrying its text inline is how `controls()` exercises this same
    assembly without writing a file. Nothing else sets it.
    """
    read = []
    for source in sorted(sources, key=lambda s: s["rank"]):
        entry = dict(source)
        if "text" in source:
            state, text, mtime = PRESENT, source["text"], None
            entry["path_name"] = source["name"]
        else:
            path, refusal = _resolve(source, root, ops, ops_state)
            if path is None:
                state, text, mtime = refusal, None, None
                entry["path_name"] = source["name"]
            else:
                got = read_source(path)
                state, text, mtime = got["state"], got["text"], got["mtime"]
                entry["path_name"] = os.path.basename(path)
        parsed = {"blocks": 0, "superseded": 0, "rows": {}, "stamp": None}
        if state == PRESENT and text:
            parsed = verdicts_from_text(text)
            if not parsed["rows"]:
                # Read in full and understood as holding no verdict block.
                # A fourth kind of nothing, and the one that is easiest to
                # mistake for a page with nothing to say.
                state = NO_BLOCK
        entry.update(parsed)
        entry["state"] = state
        entry.update(_as_of(parsed["stamp"], mtime, now))
        entry["answered"] = sorted(parsed["rows"])
        read.append(entry)
    return read


def _assemble(chain, now, poison=None):
    """Nine rows, from the first source that holds each one.

    `poison` is the reason every verdict is UNKNOWN regardless of what was
    read - a failed self-control. The recorded words are kept even then: the
    reader is what is untrusted, not the artifact, and discarding what the
    file said would destroy information instead of flagging it.
    """
    del now
    rows = []
    for criterion in CRITERIA:
        number = criterion["number"]
        label, _why = LOCATION_TEXT[criterion["location"]]
        row = dict(criterion)
        row["location_label"] = label
        row["location_why"] = LOCATION_TEXT[criterion["location"]][1]
        answer = None
        for source in chain:
            if number in source["rows"]:
                answer = (source, source["rows"][number])
                break
        if answer is None:
            row.update({
                "verdict": UNKNOWN, "recorded": None, "line": None,
                "source_key": None, "source_name": None, "source_kind": None,
                "source_where": None, "as_of": None,
                "as_of_kind": AS_OF_NONE, "age_seconds": None,
                "as_of_in_future": False, "stale": False,
                "reason": _no_source_reason(chain)})
        else:
            source, found = answer
            row.update({
                "verdict": found["verdict"], "recorded": found["recorded"],
                "line": found["line"], "source_key": source["key"],
                "source_name": source["name"], "source_kind": source["kind"],
                "source_where": source["where"], "as_of": source["as_of"],
                "as_of_kind": source["as_of_kind"],
                "age_seconds": source["age_seconds"],
                "as_of_in_future": source["as_of_in_future"],
                "stale": source["stale"], "reason": found["reason"]})
        if poison:
            row["verdict"] = UNKNOWN
            row["reason"] = poison + (
                " The recorded answer is still shown, because what is "
                "untrusted here is this page's reader and not the artifact."
                if row["recorded"] else "")
        row["verdict_label"] = VERDICT_TEXT[row["verdict"]][0]
        row["verdict_why"] = VERDICT_TEXT[row["verdict"]][1]
        rows.append(row)
    return rows


def _no_source_reason(chain):
    """Why no verdict was found, naming every authority and its state.

    Named rather than summarised, because "no data" and "the one file that
    answers this has not been written yet" are different sentences and only
    one of them tells a reader what to do next.
    """
    parts = ["%s is %s" % (source["name"], source["state"])
             for source in chain]
    return ("no recorded verdict for this criterion in any of the %d "
            "authorities consulted: %s" % (len(chain), "; ".join(parts)))


# ------------------------------------------------------------- the controls
#
# THREE CHECKS THAT RUN ON EVERY RENDER. This lane's B7 finding is that an
# instrument which sees nothing reports clean, and a reader that answered
# UNKNOWN to everything would satisfy every refusal above while being
# worthless. These are the measurement that it does not.
#
# They run the SAME assembly the page runs - `_read_chain` then `_assemble` -
# so a control passing is evidence about the real path and not about a
# parallel one written to be green.

#: A path that must not exist, for the absence control. Under `docs/` so it
#: is obvious what it is for if anybody ever meets it, and asserted absent by
#: the control itself: if somebody creates it the control FAILS rather than
#: quietly measuring nothing.
ABSENT_FIXTURE = "docs/fixtures/exit-criteria-control-file-that-must-not-exist.md"

#: A document that is present, readable, and holds no verdict block - in its
#: most dangerous shape, which is one that LOOKS like a table. Three numbered
#: rows is below `MIN_BLOCK`, so a reader with a weaker threshold would
#: accept it and report two of these as MET.
UNPARSEABLE_FIXTURE = """# EXIT CRITERIA - 2026-10-16

The re-audit did not finish. Nothing below is a verdict and the table is
not written yet.

    3  li1 renders a real note     MET
    5  write paths through the gate  MET
"""

#: The planted verdicts, and they run in BOTH directions on purpose. A
#: control that only planted MET would pass on a reader that answers MET to
#: everything - the opposite blindness, and the dangerous one.
PLANTED = {1: MET, 2: NOT_MET, 3: MET, 4: NOT_MET, 5: MET,
           6: NOT_MET, 7: MET, 8: NOT_MET, 9: MET}


def _planted_fixture():
    lines = ["## A PLANTED FIXTURE - 2026-10-16", ""]
    for number in sorted(PLANTED):
        lines.append("    %d  planted criterion %d   %s"
                     % (number, number,
                        "MET" if PLANTED[number] is MET else "NOT MET"))
    return "\n".join(lines) + "\n"


def _control_chain(source, now):
    return _assemble(_read_chain([source], REPO_ROOT, REPO_ROOT, PRESENT,
                                 now), now)


def controls(now=None):
    """The three controls, each with a PASS or a FAIL and a reason.

    A FAIL here is not a footnote: `report` turns every verdict on the page
    UNKNOWN, because a reader that cannot demonstrate it works has no
    standing to report a pass.
    """
    now = now or datetime.datetime.now()
    results = []

    # 1. An absent source renders UNKNOWN. Nothing is deleted - the fixture
    #    path is one that must never exist, and the control fails if it does.
    path = os.path.join(REPO_ROOT, ABSENT_FIXTURE)
    exists = os.path.exists(path)
    rows = _control_chain(
        {"key": "control-absent", "name": ABSENT_FIXTURE, "rank": 1,
         "where": LOC_REPO, "kind": "a control fixture"}, now)
    verdicts = {row["verdict"] for row in rows}
    ok = (not exists) and verdicts == {UNKNOWN} and len(rows) == len(CRITERIA)
    results.append({
        "name": "absent_renders_unknown",
        "what": "a criterion whose source file is absent renders UNKNOWN",
        "ok": ok,
        "detail": ("the fixture path exists, so this control measures "
                   "nothing" if exists else
                   "all %d rows UNKNOWN from an absent source" % len(rows)
                   if ok else
                   "an absent source produced %s" % sorted(verdicts))})

    # 2. A source that is present and cannot be parsed renders UNKNOWN.
    rows = _control_chain(
        {"key": "control-unparseable", "name": "unparseable-fixture.md",
         "rank": 1, "where": LOC_REPO, "kind": "a control fixture",
         "text": UNPARSEABLE_FIXTURE}, now)
    verdicts = {row["verdict"] for row in rows}
    ok = verdicts == {UNKNOWN}
    results.append({
        "name": "unparseable_renders_unknown",
        "what": "a criterion whose source is present but unparseable "
                "renders UNKNOWN",
        "ok": ok,
        "detail": ("all %d rows UNKNOWN from a source that looks like a "
                   "table and is not" % len(rows) if ok else
                   "an unparseable source produced %s" % sorted(verdicts))})

    # 3. A planted set comes back exactly as planted. Without this one the
    #    two above are satisfied by a reader that is simply always UNKNOWN.
    rows = _control_chain(
        {"key": "control-planted", "name": "planted-fixture.md", "rank": 1,
         "where": LOC_REPO, "kind": "a control fixture",
         "text": _planted_fixture()}, now)
    got = {row["number"]: row["verdict"] for row in rows}
    wrong = sorted(number for number, want in PLANTED.items()
                   if got.get(number) is not want)
    results.append({
        "name": "a_planted_met_renders_met",
        "what": "a planted MET renders MET and a planted NOT MET renders "
                "NOT MET, so the reader is not simply always UNKNOWN",
        "ok": not wrong,
        "detail": ("%d planted verdicts read back exactly, in both "
                   "directions" % len(PLANTED) if not wrong else
                   "criteria %s did not read back as planted"
                   % ", ".join(str(n) for n in wrong))})
    return results


# ---------------------------------------------------------------- the report

def report(root=None, now=None, sources=None):
    """The nine rows, their sources, and the controls that watched the read.

    Read-only and side-effect-free: no file is written, no provider is
    reached, no socket is opened and no credential is read.
    """
    root = root or REPO_ROOT
    now = now or datetime.datetime.now()
    ops, ops_state = ops_root()

    # The controls run FIRST, and `controls` is looked up on the module at
    # call time so a test can break one and watch the poisoning happen.
    checks = controls(now=now)
    failed = [check["name"] for check in checks if not check["ok"]]
    poison = None
    if failed:
        poison = ("this page's own control(s) %s FAILED, so its reader "
                  "cannot be shown to work and NO verdict it produces may "
                  "be believed. Every row is UNKNOWN until that is fixed."
                  % ", ".join(failed))

    chain = _read_chain(sources or SOURCES, root, ops, ops_state, now)
    rows = _assemble(chain, now, poison=poison)
    tally = {MET: 0, NOT_MET: 0, UNKNOWN: 0}
    for row in rows:
        tally[row["verdict"]] += 1

    data = {
        "rendered_at": now.replace(microsecond=0).isoformat(" "),
        "ops_state": ops_state,
        # The directory's NAME, never its path. A screen printing an absolute
        # path is a screen naming somebody's home directory in a screenshot.
        "ops_name": os.path.basename(ops.rstrip("\\/")) if ops else None,
        "variable": OPS_DIR,
        "controls": checks,
        "controls_ok": not failed,
        "controls_failed": failed,
        "sources": chain,
        "rows": rows,
        "tally": tally,
        "superseded": sum(source["superseded"] for source in chain),
        # The glossaries come from this module, so the renderer holds no
        # table of its own and cannot drift from the reader.
        "verdict_glossary": [{"label": label, "why": why}
                             for label, why in VERDICT_TEXT.values()],
        "location_glossary": [{"label": label, "why": why}
                              for label, why in LOCATION_TEXT.values()],
        "stale_seconds": STALE_SECONDS,
    }
    data.update(_registry_check(root, ops, ops_state, now))
    # THE SENTENCE THAT IS THE WHOLE POINT. CANARY-01 activates only when all
    # nine are met, so anything other than nine MET means it does not go -
    # and an UNKNOWN is never allowed to read as a pass on the way there.
    data["all_nine_met"] = tally[MET] == len(CRITERIA)
    return data


def describe(data=None):
    """The nine as text, for a terminal. Same reader, same refusals."""
    data = data if data is not None else report()
    out = ["CANARY-01 exit criteria - read at %s" % data["rendered_at"], ""]
    for check in data["controls"]:
        out.append("  %-4s %-30s %s"
                   % ("PASS" if check["ok"] else "FAIL",
                      check["name"], check["detail"]))
    out.append("")
    if not data["controls_ok"]:
        out.append("  THE READER IS NOT TRUSTWORTHY: every verdict below is "
                   "UNKNOWN because a control failed.")
        out.append("")
    for row in data["rows"]:
        out.append("  %d  %-8s %-28s as of %s%s"
                   % (row["number"], row["verdict_label"],
                      (row["source_name"] or "no source")[:28],
                      row["as_of"] or "UNKNOWN",
                      "  STALE" if row["stale"] else ""))
        if row["reason"]:
            out.append("        " + row["reason"][:150])
    out.append("")
    out.append("  %d MET, %d NOT MET, %d UNKNOWN - all nine met: %s"
               % (data["tally"][MET], data["tally"][NOT_MET],
                  data["tally"][UNKNOWN],
                  "YES" if data["all_nine_met"] else "NO"))
    if data["registry_drift"]:
        out.append("  DRIFT: " + data["registry_drift"])
    return "\n".join(out)


if __name__ == "__main__":                                  # pragma: no cover
    print(describe())
