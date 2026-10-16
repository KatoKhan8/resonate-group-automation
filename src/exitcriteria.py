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

#: A verdict the authority itself records as struck through, withdrawn, void
#: or superseded. NOT the value it held before, and not UNKNOWN either - those
#: are different sentences. UNKNOWN says nobody measured it; WITHDRAWN says
#: somebody measured it, wrote a verdict down, and then took it back. A page
#: that renders the second as the first loses the one fact a reader needs,
#: which is that the row USED to say something else and the change was
#: deliberate. TASK 0090's rule, and `EXIT-CRITERIA-2026-10-16.md` line 460
#: is the live instance: `~~MET at e84108f5d~~ SUPERSEDED -> UNKNOWN`.
WITHDRAWN = "withdrawn"

#: A verdict whose MEASUREMENT DATE cannot be established at all. Its own
#: state, and never the value it carried: "MET" with no date is not a verdict,
#: it is a memory, and this estate has already been wrong twice from re-reading
#: an undated claim instead of re-measuring it. Distinct from `row["stale"]`,
#: which is the age FLAG on a dated verdict - a dated verdict that is 26 hours
#: old still has a verdict; an undated one does not.
STALE = "stale"

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
    WITHDRAWN: ("WITHDRAWN",
                "the authority recorded a verdict here and then took it "
                "back - struck through, superseded, void or withdrawn. The "
                "value it held before is shown as history and is NOT the "
                "verdict: a page that silently resurrects a withdrawn MET "
                "is worse than a page that omits the row. WITHDRAWN is not "
                "met, so the canary does not go on it"),
    STALE: ("STALE",
            "a verdict was found and NO measurement date could be "
            "established for it, from the document or from the file. An "
            "undated verdict is a memory rather than a measurement, so the "
            "words recorded are shown as history and the cell is STALE - "
            "never the value it carried, and never MET"),
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

#: Which task id was found and where. The two are kept apart because a task
#: named in the block's own section measured THAT block, while one named only
#: in the document's front matter measured the document - and on a file
#: holding two passes of a re-audit those are not the same claim.
TASK_SECTION = "section"
TASK_DOCUMENT = "document"
TASK_NONE = "none"

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

#: The first artifact in this estate that answers ALL NINE in one tree, at
#: one SHA, in one run - produced by an instrument, `scripts/exit_nine.py`,
#: rather than by prose in a lane file. MET 3, NOT MET 3, UNKNOWN 3, exit 2.
#:
#: IT APPEARED FIFTEEN MINUTES AFTER TASK 0090 CLOSED, and that is the whole
#: reason this module gained a cross-file rule. `0090` proved the page is a
#: LIVE read - every authority reopened on every call, no verdict cached.
#: That bought nothing here: a live read of a stale authority SET is still
#: stale, and measured at `c6ac4b88c` the page had never opened this file.
#: Its silence about it was ignorance, not agreement.
#:
#: RANKED SECOND, NOT FIRST, AND THAT IS DELIBERATE. It is the more complete
#: authority and it is not the DESIGNATED one; which file is designated is
#: the operator's sentence to write, not this page's. Rank now decides far
#: less than it did: two authorities that disagree render UNKNOWN whatever
#: their ranks, so rank only picks which reading is quoted first when they
#: AGREE - and then both are named anyway.
AT_ONCE = "EXIT-NINE-AT-ONCE-2026-10-16.md"

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
    {"key": AT_ONCE, "name": AT_ONCE, "rank": 2, "where": LOC_OPS,
     "kind": "all nine evaluated once, in one tree, at one SHA, by an "
             "instrument rather than by prose - MET 3, NOT MET 3, UNKNOWN 3, "
             "and the run exits 2, which means the conjunction was NOT "
             "established"},
    {"key": IN_REPO_AUDIT, "name": IN_REPO_AUDIT, "rank": 3,
     "where": LOC_REPO,
     "kind": "pilotcaps TASK 0160's committed audit of the nine as a set. "
             "In git, so a clone can reconstruct it - if the clone holds "
             "the branch it was committed to"},
    {"key": LANE_REPORT, "name": LANE_REPORT, "rank": 4, "where": LOC_OPS,
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

#: A markdown strike-through span. Its contents are a verdict the authority
#: has CROSSED OUT, and before TASK 0090 the `MET` inside
#: `~~**MET at e84108f5d**~~` was harvested as one of criterion 9's live
#: verdicts. Non-greedy and single-line, so two struck spans on one row are
#: two spans and not one span swallowing the live verdict between them.
_STRUCK = re.compile(r"~~(.+?)~~")

#: The words an authority uses to take a verdict back without striking it
#: through. UPPERCASE ONLY, for the same reason `_TOKEN` is: these documents
#: argue about withdrawals in lower-case prose on nearly every page, and a
#: case-insensitive reader would mark live rows withdrawn out of sentences.
#:
#: `SUPERSEDED` earns its place from the live artifact - line 460 carries
#: `SUPERSEDED` and no `WITHDRAWN` - and `REVOKED` from this estate's other
#: habit: 220 approvals were "revoked with the reason written into the
#: record" on 2026-10-02.
_WITHDRAWAL = re.compile(r"\b(WITHDRAWN|SUPERSEDED|VOID|REVOKED)\b")

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
    """Every LIVE verdict phrase on the line, verbatim and in order.

    Struck-through spans are removed before tokenising, so a crossed-out
    verdict is never counted as a live one. They are not discarded - see
    `_struck_on`, which reports them for the WITHDRAWN row.
    """
    return [match.group(0) for match in _TOKEN.finditer(_live_part(line))]


#: A markdown table cell holding NOTHING BUT a verdict, once emphasis,
#: code quoting and whitespace are stripped. `**NOT MET**` is one; a
#: sentence mentioning MET is not.
#:
#: WHY A CELL AND NOT THE LINE, MEASURED. `EXIT-NINE-AT-ONCE-2026-10-16.md`
#: states criterion 9 as `**NOT MET**` in its verdict column, and its
#: condition column on the same row says "the whole reason 9 once read MET
#: while the default was never exercised". Reading the whole line harvested
#: both, contested them, and rendered UNKNOWN - so an authority that could
#: not be clearer was reported as unanswered. A verdict table has a verdict
#: COLUMN; its commentary column is commentary.
_CELL_STRIP = "*`_ " + chr(9)


def _cell_tokens_on(line):
    """Verdict phrases from cells that are NOTHING BUT a verdict, in order.

    Empty for a row whose verdict is written inline inside a prose cell -
    which is the shape of `EXIT-CRITERIA-2026-10-16.md`, where criterion 9's
    cell is `**NOT MET - the two trees disagree.** The Q2 plant is CLOSED
    ...`. That file must keep reading exactly as it did, so the caller falls
    back to the whole line when this returns nothing rather than treating an
    empty answer as "no verdict".

    THE RESIDUAL HAZARD, NAMED. Preferring the cell means a row whose
    commentary contradicts its own verdict column now reads the column. In
    the one direction that matters - a withdrawal - nothing changes, because
    `_struck_on` and `_withdrawals_on` still read the WHOLE line, so a
    `~~MET~~` or a `SUPERSEDED` anywhere in the row still marks it. What is
    no longer read is unmarked prose, and prose arguing about a verdict is
    not the verdict. Two verdict CELLS that differ still contest, which is
    `a_table_cell_with_two_verdicts_contests`.
    """
    live = _live_part(line)
    if not live.lstrip().startswith("|"):
        return []
    found = []
    for cell in live.split("|"):
        bare = cell.strip().strip(_CELL_STRIP).strip()
        if not bare:
            continue
        tokens = [match.group(0) for match in _TOKEN.finditer(bare)]
        if len(tokens) == 1 and _normalise(tokens[0]) == _normalise(bare):
            found.append(tokens[0])
    return found


def _live_part(line):
    """The line with every struck-through span replaced by tildes.

    Replaced rather than deleted, so removing `~~MET~~` cannot splice two
    halves of the line together and manufacture a phrase that was never
    written - `MET~~ x ~~WITH CAVEAT` becoming `MET WITH CAVEAT` is exactly
    the kind of accident a delete would cause.

    AND NOT BLANKED WITH SPACES, which was the first attempt and was measured
    wrong: `MET       WITH CAVEAT` still matches `MET[\\s-]+WITH[\\s-]+CAVEAT`,
    so padding with whitespace re-created the phrase it was meant to prevent.
    `~` is a non-word character, so `\\b` boundaries still fall either side of
    a real token, and no verdict phrase in `_TOKEN` can span one.
    """
    return _STRUCK.sub(lambda match: "~" * len(match.group(0)), line)


def _struck_on(line):
    """Every verdict phrase inside a struck-through span, verbatim."""
    found = []
    for span in _STRUCK.finditer(line):
        found.extend(match.group(0) for match in _TOKEN.finditer(span.group(1)))
    return found


def _withdrawals_on(line):
    """Every withdrawal word on the line, verbatim.

    Read from the LIVE part only. A withdrawal word inside a struck span is
    itself crossed out - a withdrawal that was taken back - and the struck
    verdict beside it already marks the row, so counting it twice would
    change nothing and mean something it does not.
    """
    return [match.group(1) for match in _WITHDRAWAL.finditer(_live_part(line))]


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
    """One row's verdict from its recorded phrases. Fails closed, loudly.

    WITHDRAWAL IS TESTED FIRST, and before the contested check rather than
    after it. Criterion 9's real row carries a struck `MET`, the word
    `SUPERSEDED`, a live `UNKNOWN` and a live `NOT MET`, and under the old
    order it came out UNKNOWN-because-contested - the right colour for the
    wrong reason, which reads to an operator as "nobody measured this" when
    the truth is "somebody measured it, wrote MET, and took it back". Those
    are different instructions to whoever reads the page.
    """
    struck = row.get("struck") or []
    withdrawals = row.get("withdrawn") or []
    if struck or withdrawals:
        held = " / ".join(struck) if struck else None
        marked = (", ".join(sorted(set(withdrawals))) if withdrawals
                  else "struck through")
        # IS THE ROW'S VERDICT WITHDRAWN, OR IS A PREVIOUS ONE? Those are
        # different rows and the first version of this did not tell them
        # apart - it rendered WITHDRAWN whenever a strike-through appeared
        # anywhere on the line, which HID a live verdict behind the history
        # of the one it replaced.
        #
        # MEASURED, and it is why this comment exists. At 03:13:49 on
        # 2026-10-16, mid-task, pilotcaps' TASK 0225 rewrote criterion 9 to
        # `**NOT MET - the two trees disagree** ... ~~UNKNOWN at e84108f5d~~`.
        # The authority's verdict there is NOT MET and what it struck is the
        # UNKNOWN that came before. Rendering that row WITHDRAWN would have
        # replaced a current refusal with a statement about a dead one.
        #
        # So: ONE unambiguous live verdict beside the withdrawal IS the
        # verdict, and the struck value travels with the row as history -
        # which is what makes a resurrection impossible either way. No
        # legible live verdict, or more than one, and the row is WITHDRAWN.
        # AND THE WITHDRAWN VALUE HAS TO BE IDENTIFIABLE AS A DIFFERENT ONE.
        # A STRIKE-THROUGH says which value is dead; a withdrawal WORD on its
        # own does not. `MET - SUPERSEDED` most naturally means *the MET* is
        # superseded, and the first attempt at this read it as a live MET with
        # a withdrawal somewhere nearby - which is precisely the failure this
        # state exists to prevent. So a live verdict is a REPLACEMENT only
        # when a struck token names a different value.
        live = {_normalise(token) for token in row["tokens"]}
        struck_values = {_normalise(token) for token in struck}
        if len(live) == 1 and struck_values and not (live & struck_values):
            only = live.pop()
            verdict = _MEANING.get(only)
            if verdict is not None:
                return verdict, row["tokens"][0], (
                    "the authority replaced an earlier verdict here: `%s` is "
                    "%s and %s is what the row records now. The struck value "
                    "is shown as history and is never this cell's verdict."
                    % (held, marked, row["tokens"][0]))
        if not held and row["tokens"]:
            # The withdrawal word applies to the verdict on this row, so
            # THAT is the value it held. Said explicitly: a row reading
            # `MET - SUPERSEDED` must report MET as the history, or the page
            # says a verdict was withdrawn and cannot say which.
            held = " / ".join(row["tokens"])
        return WITHDRAWN, held, (
            "the authority records this verdict as %s. The value it held "
            "before is %s and is shown as history, not as the verdict: a "
            "withdrawn MET that renders as MET is the one failure on this "
            "page that puts mail in front of prospects. %s"
            % (marked,
               "`%s`" % held if held else
               "not legible from the row - the strike-through or the "
               "withdrawal word carries no verdict phrase this page can read",
               ("The row also records %s - more than one answer, so none of "
                "them is promoted to the verdict: picking between two "
                "replacements on a struck row is this page deciding rather "
                "than reading." % " / ".join(row["tokens"]))
               if row["tokens"] else
               "The row records no live verdict beside the withdrawal, so "
               "nothing has replaced it yet."))
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


#: Headings that say "what follows is kept for the record and is NOT the
#: current entry". UPPERCASE, matched as whole words on the heading line only.
#:
#: WHY THIS EXISTS, MEASURED. `EXIT-CRITERIA-2026-10-16.md` is not
#: append-only. Its live table is at line 22 under `## 0. THE TABLE - SECOND
#: PASS`, and the first pass is retained verbatim at line 456 under
#: `# APPENDIX - FIRST PASS, 01:11, RETAINED VERBATIM`. "The last block wins"
#: therefore took the FIRST PASS - the side of a verdict change that was kept
#: as history - and the two passes agreeing on all three verdicts is the only
#: reason no cell was wrong. The appendix exists BECAUSE a verdict moved.
_RETAINED = re.compile(
    r"\b(APPENDIX|FIRST[\s-]+PASS|SUPERSEDED|RETAINED|HISTORIC(?:AL)?|"
    r"ARCHIVE[D]?|FOR[\s-]+THE[\s-]+RECORD|WITHDRAWN|OBSOLETE)\b")


#: A markdown filename inside a heading. A section headed with ANOTHER
#: authority document's name is reporting THAT document, and the verdicts
#: under it are not this file's own.
#:
#: MEASURED, and it is the whole reason this exists.
#: `EXIT-NINE-AT-ONCE-2026-10-16.md` holds its nine under `## 0. THE NINE`
#: and then, 158 lines later, a five-row comparison under
#: `## 4. WHERE I DISAGREE WITH EXIT-CRITERIA-2026-10-16.md AND WITH ...`.
#: "The last live block wins" took the COMPARISON: criteria 3, 4, 5 and 8
#: disappeared - including the only two nothing else in the estate answers -
#: and every surviving row carried a composite of TWO documents' verdicts,
#: so this page would have quoted the designated authority's verdict as part
#: of the new one's.
#:
#: `_RETAINED` cannot cover this. A comparison section is not history; it is
#: a report about somebody else, which is a different kind of not-mine.
#:
#: NOT A KEYWORD LIKE "DISAGREE", WHICH WAS THE FIRST ATTEMPT AND IS WORSE.
#: A heading reading `WHERE THE TWO EXPORTS DISAGREE` above a real verdict
#: table would have been dropped, and dropping the contesting block is the
#: one direction that can turn an UNKNOWN into a MET. A heading naming a
#: FILE cannot be triggered by prose about a dispute.
#:
#: Nothing is lost by skipping it: the cross-file rule below derives the
#: disagreement from both documents' OWN blocks, which is a measurement
#: rather than a reading of somebody's summary of one.
_FOREIGN_FILE = re.compile(r"\b([A-Za-z0-9][A-Za-z0-9._-]*" + chr(92) + ".md)" + chr(92) + "b")


def _foreign_by(trail, self_name):
    """The enclosing heading that names a DIFFERENT authority file, or None.

    Outermost first, matching `_retained_by`. A heading naming this file's
    own name is not foreign - a document is allowed to title itself.
    """
    mine = (self_name or "").lower()
    for _depth, heading, _index in trail:
        for found in _FOREIGN_FILE.findall(heading):
            if found.lower() != mine:
                return heading
    return None


def _retained_by(trail):
    """The enclosing heading that marks this block as history, or None.

    The OUTERMOST marked heading, so `# APPENDIX - FIRST PASS` is reported
    rather than the `## 0. THE TABLE (FIRST PASS)` nested inside it: the
    reason the block is history is the appendix, and the subheading only
    repeats it.
    """
    for _depth, heading, _index in trail:
        if _RETAINED.search(heading):
            return heading
    return None


def _is_verdict_block(block):
    """Whether a run of numbered lines is a verdict table or just a list.

    TWO SHAPES, AND THE SECOND ONE WAS A DEFECT FOUND ON LIVE DATA. A plain
    indented run has no structural marker that separates it from prose, so it
    must name a majority of the nine AND a majority of those rows must carry
    a verdict - that is what rejects the roster of nine contacts and the
    numbered list of six operator decisions, both of which are runs of
    numbered lines recording no verdict.

    A MARKDOWN TABLE IS SELF-IDENTIFYING and the majority rule is wrong for
    it. `EXIT-CRITERIA-2026-10-16.md` arrived as a three-row pipe table,
    because pilotcaps' TASK 0210 was asked to re-audit criteria 3, 5 and 9
    and nothing else. Under the majority rule the page REJECTED the
    designated authority outright and fell back to an older lane entry - so
    criterion 9 showed a stale NOT MET while the freshest measurement said
    UNKNOWN. A partial re-audit is the normal shape of this artifact, not an
    exception.

    A WITHDRAWN ROW CARRIES A VERDICT TOO, and before TASK 0090 it did not
    count as one: a table whose every row read `~~MET~~ SUPERSEDED` has no
    LIVE verdict phrase on any line, so `carrying` was 0, the whole block was
    rejected as prose, and nine rows came back UNKNOWN-because-unparseable.
    That reads as "nobody wrote this down" when the document says the
    opposite. Strike-through and withdrawal words therefore count toward the
    threshold - and this can only ever ADMIT rows that resolve to WITHDRAWN
    or UNKNOWN, because a block admitted on withdrawal evidence alone has no
    live `MET` on it by construction.
    """
    rows = block["rows"].values()
    carrying = len([row for row in rows
                    if row["tokens"] or row.get("struck")
                    or row.get("withdrawn")])
    if carrying < 1:
        return False
    if block.get("piped"):
        # A pipe-delimited row starting with a criterion number and holding
        # an uppercase verdict token is unambiguous. Prose does not come in
        # table rows, so the count threshold buys nothing here - and the
        # fail-closed direction is unchanged: a misread yields UNKNOWN, and
        # only a line that genuinely contains MET or NOT MET can yield one.
        return True
    return len(block["rows"]) >= MIN_BLOCK and carrying >= MIN_BLOCK


#: What "this document holds no verdict block" looks like. One literal, used
#: by both the parser and the chain, because two hand-written copies of this
#: shape is how a key comes to exist on one path and not the other - and a
#: missing key on a safety page is a `KeyError` in a renderer at best.
_NO_VERDICTS = {"blocks": 0, "superseded": 0, "retained_blocks": 0,
                "retained": None, "foreign_blocks": 0, "foreign": None,
                "rows": {}, "stamp": None, "task": None,
                "task_kind": TASK_NONE, "task_where": None}


def verdicts_from_text(text, self_name=None):
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

    # The heading trail, so a block knows which sections enclose it. A
    # heading at depth N closes every deeper one - that is what lets the
    # `# APPENDIX` at depth 1 govern the `## 0. THE TABLE (FIRST PASS)` at
    # depth 2 beneath it, and stop governing anything once a later depth-1
    # heading appears.
    trail = []
    for index, raw in enumerate(lines):
        if raw.strip().startswith("#"):
            # A heading always ends a block. Two short runs either side of one
            # are two runs, never a single table that happens to span it.
            close()
            depth = len(raw.strip()) - len(raw.strip().lstrip("#"))
            trail = [entry for entry in trail if entry[0] < depth]
            trail.append((depth, raw.strip(), index))
            continue
        number = number_on(raw)
        tokens = _tokens_on(raw)
        # A TABLE ROW'S OWN VERDICT COLUMN OUTRANKS ITS PROSE COLUMNS,
        # and only when it HAS one - an empty answer here is 'this row
        # writes its verdict inline', not 'this row has no verdict'.
        celled = _cell_tokens_on(raw)
        if celled:
            tokens = celled
        struck = _struck_on(raw)
        withdrawn = _withdrawals_on(raw)
        if number is not None:
            if current is None:
                current = {"rows": {}, "order": [], "start": index,
                           "trail": list(trail),
                           "retained": _retained_by(trail),
                           # Which OTHER authority this section is about,
                           # if any. Not history - a report on somebody
                           # else, whose verdicts are theirs.
                           "foreign": _foreign_by(trail, self_name),
                           # Whether this block is a markdown table. Set from
                           # the FIRST criterion row and required of all of
                           # them, so a table with one stray indented line
                           # does not become a one-row table block.
                           "piped": raw.lstrip().startswith("|")}
            elif not raw.lstrip().startswith("|"):
                current["piped"] = False
            if number in current["rows"]:
                # The same criterion twice inside one block. Not collapsed:
                # the phrases accumulate, so two different answers come out
                # CONTESTED rather than last-one-wins.
                current["rows"][number]["tokens"].extend(tokens)
                current["rows"][number]["struck"].extend(struck)
                current["rows"][number]["withdrawn"].extend(withdrawn)
            else:
                current["rows"][number] = {
                    "number": number, "line": raw.rstrip(),
                    "tokens": list(tokens), "struck": list(struck),
                    "withdrawn": list(withdrawn)}
                current["order"].append(number)
            gap = 0
        elif current is not None and current["piped"] \
                and not raw.lstrip().startswith("|") \
                and (tokens or struck or withdrawn) and _indented(raw):
            # A MARKDOWN TABLE ROW HAS NO CONTINUATION LINES, and before
            # TASK 0120 this branch did not know that. Continuation exists
            # for TASK 0160's INDENTED block shape, where a row's verdict
            # may sit on the line below its number. A pipe table's cells are
            # closed by its pipes.
            #
            # MEASURED, on `EXIT-NINE-AT-ONCE-2026-10-16.md`. Its nine-row
            # table is followed by a blank line and then
            #
            #     `    tally   MET 3   NOT MET 3   UNKNOWN 3`
            #
            # which is indented and carries three verdict tokens, so all
            # three were appended to the LAST ROW SEEN - criterion 9 - and a
            # cell stating `**NOT MET**` unambiguously came out
            # `NOT MET / MET / MET / NOT MET / UNKNOWN`, which contests to
            # UNKNOWN. A summary line belongs to no row.
            #
            # THE DIRECTION, NAMED RATHER THAN CLAIMED SAFE. Every other
            # refusal in this module leans towards UNKNOWN; this one can
            # reveal a verdict an absorbed line was hiding, and on the live
            # artifact it reveals NOT MET. That is not a weakened guard: a
            # line that is not part of the table is a MISREAD, and a misread
            # is the defect in either direction. The within-row contest rule
            # is untouched - two verdicts in one TABLE CELL still render
            # UNKNOWN - and `a_table_cell_with_two_verdicts_contests` is the
            # control that watches it.
            gap += 1
            if gap > MAX_GAP:
                close()
        elif current is not None and (tokens or struck or withdrawn) \
                and _indented(raw):
            if current["order"]:
                last = current["rows"][current["order"][-1]]
                last["tokens"].extend(tokens)
                last["struck"].extend(struck)
                last["withdrawn"].extend(withdrawn)
            gap = 0
        elif current is not None:
            gap += 1
            if gap > MAX_GAP:
                close()
    close()

    if not blocks:
        return dict(_NO_VERDICTS)

    # THE LAST LIVE BLOCK WINS, not the last block. A block under a heading
    # that calls itself an appendix, a first pass or superseded is history
    # whatever its position in the file, and a document that keeps its old
    # answer below its new one is the normal shape here rather than an
    # exception. Fail-closed direction unchanged: if EVERY block is marked
    # history the last one is still read, because refusing the whole document
    # would turn a readable authority into nine UNKNOWNs - but `retained`
    # travels with the answer so the page can say so.
    live = [block for block in blocks
            if not block["retained"] and not block["foreign"]]
    winner = (live or blocks)[-1]
    rows = {}
    for number, row in winner["rows"].items():
        verdict, recorded, reason = _decide(row)
        rows[number] = {"number": number, "verdict": verdict,
                        "recorded": recorded, "reason": reason,
                        "line": row["line"],
                        "struck": list(row.get("struck") or []),
                        "withdrawn": sorted(set(row.get("withdrawn") or []))}
    return {"blocks": len(blocks), "superseded": len(blocks) - 1,
            "retained_blocks": len([block for block in blocks
                                    if block["retained"]]),
            "retained": winner["retained"],
            "foreign_blocks": len([block for block in blocks
                                   if block["foreign"]
                                   and not block["retained"]]),
            "foreign": winner["foreign"],
            "rows": rows,
            "stamp": _stamp_above(lines, winner["start"], winner["trail"]),
            **_task_for(lines, winner)}


def _scope(start, trail):
    """The line numbers a block's date and task may be read from, in order.

    THE SEARCH STOPS AT THE BLOCK'S OWN SECTION, AND THEN TAKES ONLY
    HEADINGS. Before TASK 0090 it walked every line upward without limit, so
    criterion 9's block at line 456 of `EXIT-CRITERIA-2026-10-16.md` reached
    line 435 - a `TASK 0220` correction about `glm/0068`, dated 2026-10-15
    22:40 - and that became the `as of` on the freshest authority in the
    estate, with a red STALE badge beside it.

    Two kinds of line may carry a block's date, and prose in another section
    is neither:

      1. the lines between the block and its own nearest heading, and that
         heading itself - the prose directly introducing this table;
      2. the lines of the ENCLOSING headings, outward, and only those lines.
         This is what a lane file needs and the first rule alone would lose:
         `LANE-pilotcaps.md`'s verdict table sits under
         `## THE NINE, RE-MEASURED ON ...`, which names no date, seven
         subheadings below `# 2026-10-16 - TASK 0200 (pilotcaps)`, which
         names both. A heading is a statement about everything beneath it;
         the paragraphs under a SIBLING heading are not.
    """
    nearest = trail[-1][2] if trail else 0
    scope = list(range(start, nearest - 1, -1))
    for _depth, _heading, index in reversed(trail[:-1]):
        scope.append(index)
    return scope


def _stamp_above(lines, start, trail=()):
    """The date for this block, from its own section then outward.

    A lane file holds dozens of entries and the date in the heading above a
    block is that entry's date. Searching the whole document for the newest
    date would hand a 2026-10-15 block today's heading; searching past the
    block's own section harvests another measurement's date, which is D3.
    """
    for index in _scope(start, trail):
        match = _DATE.search(lines[index])
        if match:
            return match.group(1)
    return None


#: A task id as this estate writes one: `TASK 0210`, `TASK-0210`, `0210`
#: inside a heading. Three or four digits, because the queue numbers briefs
#: `0010`-`0220` and a two-digit match would harvest a time or a count.
_TASK = re.compile(r"\bTASK[\s-]*0*(\d{3,4})\b")


def _task_for(lines, winner):
    """WHICH TASK measured this block, and from how close a source.

    Section 2 of TASK 0090: "MET without a date is not a verdict; it is a
    memory" - and a date without an author is barely better, because the next
    question a reader has is who to go back to. Scoped exactly like the date,
    and for the same reason: the nearest `TASK` above criterion 9's appendix
    block, unscoped, is `TASK 0220`'s correction about `glm/0068`.

    The front-matter fallback is NOT a guess. It is a weaker claim, reported
    as a weaker claim: `EXIT-CRITERIA-2026-10-16.md`'s second-pass table sits
    under `## 0. THE TABLE - SECOND PASS`, which names no task, while line 3
    of the document says `TASK 0210 (pilotcaps) ran twice`. Saying "the
    document is 0210's and the section does not say" is true; saying "this
    row was measured by 0210" would be an inference.
    """
    scope = _scope(winner["start"], winner["trail"])
    for index in scope:
        match = _TASK.search(lines[index])
        if match:
            return {"task": "TASK " + match.group(1).zfill(4),
                    "task_kind": TASK_SECTION,
                    "task_where": lines[index].strip()[:120]}
    # The document's front matter: its title line and the prose under it, up
    # to the next heading. Bounded that way rather than by a line count,
    # because "the paragraph under the title" is a shape and "the first
    # twenty lines" is a guess.
    for index in range(0, len(lines)):
        if index and lines[index].strip().startswith("#"):
            break
        match = _TASK.search(lines[index])
        if match:
            return {"task": "TASK " + match.group(1).zfill(4),
                    "task_kind": TASK_DOCUMENT,
                    "task_where": lines[index].strip()[:120]}
    return {"task": None, "task_kind": TASK_NONE, "task_where": None}


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
        # THE PATH THIS PAGE TRIED, kept so a FAILED read can name it.
        # Carried on every entry and published only when the read failed -
        # TASK 0090 section 3 requires the absolute path on a read failure,
        # and this module's standing rule is that a healthy page prints no
        # absolute path because that is somebody's home directory in a
        # screenshot. Both hold: a reader who has to go and look is given the
        # path, and a reader who does not is not shown one.
        entry["attempted_path"] = None
        if "text" in source:
            state, text, mtime = PRESENT, source["text"], None
            entry["path_name"] = source["name"]
        else:
            path, refusal = _resolve(source, root, ops, ops_state)
            if path is None:
                state, text, mtime = refusal, None, None
                entry["path_name"] = source["name"]
            else:
                entry["attempted_path"] = os.path.abspath(path)
                got = read_source(path)
                state, text, mtime = got["state"], got["text"], got["mtime"]
                entry["path_name"] = os.path.basename(path)
        parsed = dict(_NO_VERDICTS)
        if state == PRESENT and text:
            # ITS OWN BASENAME, so a document titling itself is not read
            # as a section about a foreign authority.
            parsed = verdicts_from_text(
                text, self_name=os.path.basename(source["name"]))
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
        # EVERY source that answers this criterion, not just the first. The
        # first still ANSWERS it - rank is unchanged - but a lower-ranked
        # source saying something different is a fact about the estate, and
        # TASK 0090 section 3 requires both be shown with which is newer.
        found_in = [(source, source["rows"][number]) for source in chain
                    if number in source["rows"]]
        answer = found_in[0] if found_in else None
        readings = _readings(found_in)
        row["readings"] = readings
        row["disagreement"] = _disagreement(found_in)
        row["contested"] = bool(row["disagreement"])
        # NAMED ONLY WHEN TWO OR MORE AUTHORITIES CONCUR. One source
        # agreeing with itself is not corroboration.
        row["agreement"] = (readings if len(readings) > 1
                            and not row["disagreement"] else [])
        if answer is None:
            row.update({
                "verdict": UNKNOWN, "recorded": None, "line": None,
                "source_key": None, "source_name": None, "source_kind": None,
                "source_where": None, "as_of": None,
                "as_of_kind": AS_OF_NONE, "age_seconds": None,
                "as_of_in_future": False, "stale": False,
                "attempted_path": None, "task": None,
                "task_kind": TASK_NONE, "retained": None,
                "struck": [], "withdrawn": [],
                "off_designated": False, "designated_state": None,
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
                "stale": source["stale"], "reason": found["reason"],
                "attempted_path": source.get("attempted_path"),
                "task": source["task"], "task_kind": source["task_kind"],
                "retained": source["retained"],
                "struck": list(found.get("struck") or []),
                "withdrawn": list(found.get("withdrawn") or []),
                "off_designated": False, "designated_state": None})
            # A DESIGNATED AUTHORITY THAT IS SILENT DOES NOT VETO.
            # Criteria 4 and 8 are the live instance: nothing in the
            # page's set answered either until 2026-10-16 03:41, and
            # `EXIT-CRITERIA-2026-10-16.md` - a re-audit of criteria 3, 5
            # and 9 only - was never going to. So another authority's
            # answer stands, MARKED with where it came from: an unmarked
            # verdict read off a non-designated file looks exactly like
            # one read off the designated one, and those are different
            # claims.
            designated = min(chain, key=lambda item: item["rank"])
            if source["key"] != designated["key"]:
                row["off_designated"] = True
                row["designated_state"] = designated["state"]
            # AN UNDATED VERDICT IS NOT A VERDICT. Applied to MET and NOT MET
            # only: UNKNOWN and WITHDRAWN already say "this is not an answer
            # you may act on", and overwriting WITHDRAWN would throw away the
            # more specific of the two sentences.
            if (source["as_of_kind"] == AS_OF_NONE
                    and found["verdict"] in (MET, NOT_MET)):
                row["verdict"] = STALE
                row["recorded"] = found["recorded"]
                row["reason"] = (
                    "the authority records %s and NO measurement date could "
                    "be established for it - neither a date in the document "
                    "above the block nor a modification time for the file. "
                    "An undated verdict is a memory rather than a "
                    "measurement, so it renders STALE and not %s."
                    % (found["recorded"] or "a verdict",
                       VERDICT_TEXT[found["verdict"]][0]))
            # A VERDICT TWO AUTHORITIES DISPUTE RENDERS UNKNOWN / CONTESTED,
            # WHATEVER IT IS AND WHATEVER THEIR RANKS. TASK 0090 downgraded
            # a disputed MET only, on the argument that MET is the one value
            # that licenses a send. That argument is right about MET and
            # WRONG as a stopping point, and criterion 9 on 2026-10-16 is
            # why: `EXIT-CRITERIA-2026-10-16.md` records WITHDRAWN and
            # `EXIT-NINE-AT-ONCE-2026-10-16.md` records NOT MET. Neither is
            # a pass, so the old rule left it alone - and the page then
            # reported WITHDRAWN as though one authority answered, which is
            # a claim about the estate that is not true. A reader who has to
            # act needs to know the authorities do not agree on what kind of
            # failure this is.
            #
            # THE PAGE MAY NOT RESOLVE IT - not by rank, not by recency, not
            # by which document is longer. It refuses, and names both.
            if row["disagreement"]:
                row["verdict"] = UNKNOWN
                row["reason"] = (
                    "CONTESTED ACROSS AUTHORITIES: %s. This page does not "
                    "choose between them - not by rank, not by recency and "
                    "not by which document is longer - so the cell is "
                    "UNKNOWN and every reading is shown with its date and "
                    "its measuring task. UNKNOWN here means the estate does "
                    "not have one answer to this criterion, which is a "
                    "different and worse thing than nobody having measured "
                    "it."
                    % "; ".join(_named(item)
                                for item in row["disagreement"]))
            elif row["agreement"]:
                # CORROBORATION IS NAMED, and the verdict is unchanged.
                # Two authorities agreeing is not a stronger verdict - it
                # is the same verdict with a second witness, and the row
                # says who both are.
                row["reason"] = (
                    "%d authorities agree: %s. The verdict is theirs and is "
                    "not strengthened by being doubled - but a reader can "
                    "see that more than one file was opened. %s"
                    % (len(row["agreement"]),
                       "; ".join(_named(item)
                                 for item in row["agreement"]),
                       row["reason"] or ""))
        if poison:
            row["verdict"] = UNKNOWN
            row["reason"] = poison + (
                " The recorded answer is still shown, because what is "
                "untrusted here is this page's reader and not the artifact."
                if row["recorded"] else "")
        row["verdict_label"] = VERDICT_TEXT[row["verdict"]][0]
        if row.get("contested"):
            # ONE WORD MORE THAN UNKNOWN, AND IT CHANGES THE INSTRUCTION.
            # A plain UNKNOWN says nobody measured this and somebody
            # should. CONTESTED says two authorities measured it and the
            # estate has no single answer - which is not fixed by
            # measuring again, and is fixed by the operator naming an
            # authority. The verdict value is UNCHANGED at UNKNOWN, so
            # the tally keeps its five buckets and nothing here can read
            # as a sixth kind of pass.
            row["verdict_label"] = VERDICT_TEXT[UNKNOWN][0] + " / CONTESTED"
        row["verdict_why"] = VERDICT_TEXT[row["verdict"]][1]
        rows.append(row)
    return rows


def _readings(found_in):
    """Every authority that answered this criterion, in rank order.

    Built whether they agree or not, because "both authorities say NOT MET"
    is a fact a reader needs just as much as a dispute - and because a page
    that only ever names a second source when something is wrong teaches a
    reader that one name means one authority looked.
    """
    ages = [_age_key(source) for source, _row in found_in]
    newest = max((age for age in ages if age is not None), default=None)
    out = []
    for index, (source, found) in enumerate(found_in):
        out.append({
            "source_name": source["name"],
            "rank": source["rank"],
            "verdict": found["verdict"],
            "verdict_label": VERDICT_TEXT[found["verdict"]][0],
            "recorded": found["recorded"],
            "as_of": source["as_of"],
            "as_of_kind": source["as_of_kind"],
            "task": source["task"],
            "authoritative": index == 0,
            # `None` means this source's date could not be established, so it
            # is NOT the newer one and is not the older one either. Said
            # explicitly rather than sorted to the bottom.
            "newer": (ages[index] is not None and newest is not None
                      and ages[index] == newest),
            "undated": ages[index] is None})
    return out


def _named(reading):
    """One authority's reading, as a sentence naming all three facts."""
    return ("%s says %s (as of %s, %s)"
            % (reading["source_name"], reading["verdict_label"],
               reading["as_of"] or "an unestablished date",
               reading["task"] or "no measuring task named in the file"))


def _disagreement(found_in):
    """Both readings when two authorities answer one criterion differently.

    Empty when they agree, or when only one of them answers - and empty is
    the normal case, so a reader seeing this section knows something is
    actually wrong rather than that the page always shows it.

    WHICH IS NEWER IS A SEPARATE QUESTION FROM WHICH IS AUTHORITATIVE, and
    the page shows both answers rather than merging them. On 2026-10-16 the
    designated authority records criterion 9 as WITHDRAWN and
    `LANE-pilotcaps.md` still records NOT MET: the first is the authority,
    and it is not obviously the newer, because the lane file is appended to
    every few minutes. Neither fact alone settles it, so neither is hidden.
    """
    if len({item[1]["verdict"] for item in found_in}) < 2:
        return []
    return _readings(found_in)


def _age_key(source):
    """A sortable key for a source's `as of`, or None when there is none.

    Both `as_of` shapes are ISO and sort lexicographically - a bare
    `2026-10-16` from a document stamp, and `2026-10-16 01:46:00` from a
    modification time. The date-only form sorts BEFORE any time on the same
    day, which is the conservative direction: a document that names only a
    day is not credited with being newer than a file timestamped that day.
    """
    return source["as_of"] or None


def _located(source, root, ops, ops_state):
    """A source's path under a NAMED root, or None when there is no path.

    `resonate-ops{sep}EXIT-NINE-AT-ONCE-2026-10-16.md` rather than the
    absolute path it was read from. Enough to go and find the file; not a
    home directory on a screen.
    """
    if "text" in source:
        return None
    if source["where"] == LOC_OPS:
        if ops_state != PRESENT or not ops:
            return None
        return os.path.join(os.path.basename(ops.rstrip(chr(92) + "/")),
                            source["name"].replace("/", os.sep))
    return os.path.join(os.path.basename(root.rstrip(chr(92) + "/")),
                        source["name"].replace("/", os.sep))


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


# ------------------------------------------------------------ the discovery
#
# THE PAGE NAMING ITS OWN BLIND SPOT. `SOURCES` is a configuration, and a
# configuration cannot know about a file written after it. On 2026-10-16
# `EXIT-NINE-AT-ONCE-2026-10-16.md` appeared at 03:41, fifteen minutes after
# the page was last audited, and the page did not disagree with it - it had
# never opened it. There is no version of this module that prevents that
# happening again. What it can do is SAY SO.
#
# ANNOUNCE, NEVER REGISTER, and that is not timidity. The same scan that
# finds the new authority finds `LANE-webapp.md` - this page's own lane file,
# whose prose about these criteria parses as a verdict block answering five
# of them. A scanner that promoted what it found would make this page an
# authority on itself, which is the one thing section 6 of the brief forbids.
# So discovery changes no verdict and no tally. It changes one sentence
# above the table, from silence to "this set may be incomplete".


def _discover(ops, ops_state, configured, entries=None):
    """Authority-shaped files on disk that the configuration does not name.

    `entries` supplies a listing inline, which is how C3 exercises this exact
    function without writing a file - the same seam `_read_chain` already
    offers `controls()`. The real `os.listdir` path is proven separately, by
    a test with a real temporary directory, because an injected listing
    cannot show that the scan looks in the right place.
    """
    known = {os.path.basename(name).lower() for name in configured}
    injected = entries is not None
    if injected:
        listing = [{"name": entry["name"], "text": entry.get("text"),
                    "state": PRESENT if entry.get("text") else EMPTY}
                   for entry in entries]
    else:
        if ops_state != PRESENT:
            # NOT "nothing was found". The page could not look, so it cannot
            # say the set is complete either - which is why `blind` below
            # drives the same notice a positive find does.
            return {"state": ops_state, "scanned": 0, "found": [],
                    "injected": False, "blind": True}
        try:
            names = sorted(os.listdir(ops))
        except OSError:
            return {"state": UNREADABLE, "scanned": 0, "found": [],
                    "injected": False, "blind": True}
        listing = []
        for name in names:
            if not name.lower().endswith(".md"):
                continue
            got = read_source(os.path.join(ops, name))
            listing.append({"name": name, "text": got["text"],
                            "state": got["state"]})
    found = []
    for item in listing:
        if os.path.basename(item["name"]).lower() in known:
            continue
        if item["state"] != PRESENT or not item["text"]:
            continue
        parsed = verdicts_from_text(
            item["text"], self_name=os.path.basename(item["name"]))
        if not parsed["rows"]:
            continue
        found.append({"name": item["name"],
                      "answered": sorted(parsed["rows"]),
                      "blocks": parsed["blocks"]})
    return {"state": PRESENT, "scanned": len(listing), "found": found,
            "injected": injected, "blind": False}


# ------------------------------------------------------------ the conjunction
#
# CANARY-01 activates only when all nine are true, so the nine have ONE
# answer and it is a conjunction rather than a score. `EXIT-NINE-AT-ONCE-
# 2026-10-16.md` exits **2** on exactly this question, and its own C3 control
# pins the dominance order this reproduces: nine MET is MET, one NOT MET
# takes it to NOT MET, and ONE UNKNOWN DOMINATES EIGHT PASSES rather than
# being outvoted by them.
#
# "3 of 9 are MET" is a partial pass written as a fraction, and a fraction
# invites a reader to feel two thirds of the way there. There is no such
# position: the conjunction is UNKNOWN tonight and it was UNKNOWN when one
# criterion was unmeasured.


def conjunction_of(rows, complete=True):
    """The one verdict over all nine, and why.

    `complete` is False when the page has said its authority set may be
    incomplete. It can only ever move a MET to UNKNOWN: a page that has just
    announced it may not have read every authority may not then assert the
    conjunction those authorities would settle.
    """
    verdicts = [row["verdict"] for row in rows]
    if len(rows) != len(CRITERIA):
        return UNKNOWN, (
            "the page assembled %d rows and CANARY-01 has %d criteria, so "
            "the SET is wrong and no conjunction over it means anything."
            % (len(rows), len(CRITERIA)))
    unresolved = [row["number"] for row in rows
                  if row["verdict"] in (UNKNOWN, WITHDRAWN, STALE)]
    refused = [row["number"] for row in rows if row["verdict"] == NOT_MET]
    if unresolved:
        return UNKNOWN, (
            "criteri%s %s %s not established, so the CONJUNCTION was not "
            "established. This is not %d of %d and it is not nearly there: "
            "one unresolved criterion dominates any number of passes, "
            "because an unreadable or disputed authority means UNKNOWN and "
            "UNKNOWN never becomes PASS.%s"
            % ("on" if len(unresolved) == 1 else "a",
               ", ".join(str(n) for n in unresolved),
               "is" if len(unresolved) == 1 else "are",
               len(rows) - len(unresolved) - len(refused), len(rows),
               (" Criteri%s %s %s recorded NOT MET as well."
                % ("on" if len(refused) == 1 else "a",
                   ", ".join(str(n) for n in refused),
                   "is" if len(refused) == 1 else "are")) if refused else ""))
    if refused:
        return NOT_MET, (
            "every criterion is established and criteri%s %s %s NOT MET, so "
            "the conjunction is NOT MET and the canary does not go."
            % ("on" if len(refused) == 1 else "a",
               ", ".join(str(n) for n in refused),
               "is" if len(refused) == 1 else "are"))
    if not complete:
        return UNKNOWN, (
            "all %d criteria read MET from the authorities this page could "
            "enumerate - AND this page has just reported that its authority "
            "set may be incomplete. A conjunction asserted over a set the "
            "page admits it may not have read in full is exactly the claim "
            "it has no standing to make, so it is UNKNOWN." % len(rows))
    return MET, (
        "all %d criteria are recorded MET by the authorities named above. "
        "That is a reading of somebody else's measurements and is only as "
        "good as the dates beside them." % len(rows))


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

#: A verdict table carrying NO date anywhere, in a source read inline so the
#: filesystem offers no modification time either. Every row says MET, which
#: is what makes this control worth running: a reader that ignored the
#: missing date would report nine MET off it and the page would say the
#: canary goes.
UNDATED_FIXTURE = """## A FIXTURE WITH NO DATE

    1  undated criterion 1   MET
    2  undated criterion 2   MET
    3  undated criterion 3   MET
    4  undated criterion 4   MET
    5  undated criterion 5   MET
    6  undated criterion 6   MET
    7  undated criterion 7   MET
    8  undated criterion 8   MET
    9  undated criterion 9   MET
"""

#: Nine verdicts the authority has crossed out, in the two shapes this estate
#: actually writes: a strike-through span, and the word SUPERSEDED beside the
#: value it replaced. A reader without `_STRUCK` reports nine MET off this.
WITHDRAWN_FIXTURE = """## A FIXTURE OF WITHDRAWN VERDICTS - 2026-10-16

    1  ~~MET~~ SUPERSEDED
    2  ~~MET~~ SUPERSEDED
    3  ~~MET~~ SUPERSEDED
    4  ~~MET~~ SUPERSEDED
    5  ~~MET~~ SUPERSEDED
    6  ~~MET~~ SUPERSEDED
    7  ~~MET~~ SUPERSEDED
    8  ~~MET~~ SUPERSEDED
    9  ~~MET~~ SUPERSEDED
"""

#: A table of REPLACEMENTS: a struck value and the live verdict that replaced
#: it, on every row. Every one must read `NOT MET`.
#:
#: WHY THIS IS A SEPARATE CONTROL, AND IT COMES FROM A MUTATION. Deleting the
#: strike-through reader entirely - `_live_part` returning the line unchanged
#: - left `WITHDRAWN_FIXTURE` passing, because `~~MET~~ SUPERSEDED` then has
#: `MET` in BOTH the live set and the struck set, the two overlap, and the row
#: falls to WITHDRAWN for the wrong reason. A control that cannot see its own
#: reader being removed is the shape of defect this page exists to prevent.
#: This fixture does see it: with the reader gone, each row reads MET and NOT
#: MET as two live verdicts and comes back WITHDRAWN instead of NOT MET.
REPLACEMENT_FIXTURE = """## A FIXTURE OF REPLACED VERDICTS - 2026-10-16

    1  ~~MET~~ SUPERSEDED -> NOT MET
    2  ~~MET~~ SUPERSEDED -> NOT MET
    3  ~~MET~~ SUPERSEDED -> NOT MET
    4  ~~MET~~ SUPERSEDED -> NOT MET
    5  ~~MET~~ SUPERSEDED -> NOT MET
    6  ~~MET~~ SUPERSEDED -> NOT MET
    7  ~~MET~~ SUPERSEDED -> NOT MET
    8  ~~MET~~ SUPERSEDED -> NOT MET
    9  ~~MET~~ SUPERSEDED -> NOT MET
"""


def _planted_fixture():
    lines = ["## A PLANTED FIXTURE - 2026-10-16", ""]
    for number in sorted(PLANTED):
        lines.append("    %d  planted criterion %d   %s"
                     % (number, number,
                        "MET" if PLANTED[number] is MET else "NOT MET"))
    return "\n".join(lines) + "\n"


def _control_chain(source, now):
    """The rows a fixture source - or a LIST of them - assembles to.

    A list is what C1, C2 and C4 need: the cross-file rules cannot be
    exercised by one authority, and TASK 0090's controls all had exactly one,
    which is why none of them could have caught the set growing.
    """
    sources = source if isinstance(source, (list, tuple)) else [source]
    return _assemble(_read_chain(sources, REPO_ROOT, REPO_ROOT, PRESENT,
                                 now), now)


#: Nine piped rows carrying the given verdicts, as a dated markdown table -
#: the shape both real ops authorities use.
PAIR_DATE = "2026-10-16"


def _pair_fixture(verdicts, title):
    lines = ["## %s - %s" % (title, PAIR_DATE), "",
             "| # | criterion | verdict |", "|---|---|---|"]
    for criterion in CRITERIA:
        number = criterion["number"]
        lines.append("| %d | control criterion %d | **%s** |"
                     % (number, number,
                        VERDICT_TEXT[verdicts[number]][0]))
    return "\n".join(lines) + "\n"


def _pair_source(name, verdicts, rank, title):
    return {"key": name, "name": name, "rank": rank, "where": LOC_REPO,
            "kind": "a control fixture authority",
            "text": _pair_fixture(verdicts, title)}


#: The verdicts C1, C2 and C4 plant. C1/C2 deliberately MIX met and not-met
#: so that C4 - all nine MET - is a different measurement and not a restated
#: one: a control that plants only the value it is looking for cannot tell a
#: working reader from one that always answers that value.
PAIR_MIXED = {1: MET, 2: NOT_MET, 3: MET, 4: NOT_MET, 5: MET,
              6: NOT_MET, 7: MET, 8: NOT_MET, 9: MET}
PAIR_ALL_MET = {number: MET for number in range(1, 10)}


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

    # 4. A verdict with no establishable date renders STALE, not MET. The
    #    fixture says MET nine times, so a reader that drops the date
    #    requirement reports the canary ready off it.
    rows = _control_chain(
        {"key": "control-undated", "name": "undated-fixture.md", "rank": 1,
         "where": LOC_REPO, "kind": "a control fixture",
         "text": UNDATED_FIXTURE}, now)
    verdicts = {row["verdict"] for row in rows}
    ok = verdicts == {STALE}
    results.append({
        "name": "an_undated_verdict_renders_stale",
        "what": "a verdict with no establishable measurement date renders "
                "STALE and never the value it carried",
        "ok": ok,
        "detail": ("all %d rows STALE from a table that says MET nine times "
                   "and carries no date" % len(rows) if ok else
                   "an undated MET produced %s" % sorted(verdicts))})

    # 5. A struck-through or superseded verdict renders WITHDRAWN, not the
    #    value it held. This is criterion 9's real shape.
    rows = _control_chain(
        {"key": "control-withdrawn", "name": "withdrawn-fixture.md",
         "rank": 1, "where": LOC_REPO, "kind": "a control fixture",
         "text": WITHDRAWN_FIXTURE}, now)
    verdicts = {row["verdict"] for row in rows}
    held = {row["recorded"] for row in rows}
    ok = verdicts == {WITHDRAWN} and held == {"MET"}
    results.append({
        "name": "a_withdrawn_met_renders_withdrawn",
        "what": "a verdict the authority struck through or marked "
                "SUPERSEDED renders WITHDRAWN, with the value it held shown "
                "as history rather than as the verdict",
        "ok": ok,
        "detail": ("all %d rows WITHDRAWN, each still reporting MET as the "
                   "value it held" % len(rows) if ok else
                   "a struck-through MET produced verdicts %s holding %s"
                   % (sorted(verdicts), sorted(str(h) for h in held)))})

    # 6. A struck value beside ONE live verdict reads the live one. This is
    #    the control that watches the strike-through reader itself: control 5
    #    survives its deletion, because a reader that cannot see `~~` finds
    #    MET in both the live and the struck set and still answers WITHDRAWN.
    rows = _control_chain(
        {"key": "control-replacement", "name": "replacement-fixture.md",
         "rank": 1, "where": LOC_REPO, "kind": "a control fixture",
         "text": REPLACEMENT_FIXTURE}, now)
    verdicts = {row["verdict"] for row in rows}
    held = {tuple(row["struck"]) for row in rows}
    ok = verdicts == {NOT_MET} and held == {("MET",)}
    results.append({
        "name": "a_replacement_reads_the_replacement",
        "what": "a struck value beside ONE live verdict renders the live "
                "verdict, with the struck one kept as history - so a "
                "current refusal is not hidden behind a dead one",
        "ok": ok,
        "detail": ("all %d rows NOT MET, each still reporting the struck "
                   "MET as history" % len(rows) if ok else
                   "a replaced verdict produced %s holding %s"
                   % (sorted(verdicts), sorted(held)))})

    # C1. TWO AUTHORITIES THAT AGREE RENDER THE VERDICT AND NAME BOTH. The
    #     verdict is unchanged by corroboration - what changes is that the
    #     row can say two files were opened, which is the only way a reader
    #     can tell a concurring set from a set of one.
    rows = _control_chain(
        [_pair_source("control-pair-a.md", PAIR_MIXED, 1, "PAIR A"),
         _pair_source("control-pair-b.md", PAIR_MIXED, 2, "PAIR B")], now)
    wrong = sorted(row["number"] for row in rows
                   if row["verdict"] is not PAIR_MIXED[row["number"]])
    named = {row["number"]: {item["source_name"]
                             for item in row["agreement"]} for row in rows}
    both = {"control-pair-a.md", "control-pair-b.md"}
    unnamed = sorted(number for number, names in named.items()
                     if names != both)
    ok = not wrong and not unnamed
    results.append({
        "name": "two_agreeing_authorities_render_and_name_both",
        "what": "a criterion two live authorities answer the SAME way "
                "renders that verdict and names both files",
        "ok": ok,
        "detail": ("all %d rows rendered the agreed verdict and named both "
                   "authorities" % len(rows) if ok else
                   "verdict wrong on %s; both authorities not named on %s"
                   % (wrong or "none", unnamed or "none"))})

    # C2. TWO AUTHORITIES THAT DISAGREE RENDER UNKNOWN / CONTESTED. One row
    #     flipped, eight untouched - so a reader that simply answered
    #     CONTESTED to everything fails this as loudly as one that answered
    #     the first authority it found.
    flipped = dict(PAIR_MIXED)
    flipped[3] = NOT_MET
    rows = _control_chain(
        [_pair_source("control-pair-a.md", PAIR_MIXED, 1, "PAIR A"),
         _pair_source("control-pair-b.md", flipped, 2, "PAIR B")], now)
    by_number = {row["number"]: row for row in rows}
    three = by_number[3]
    said = {item["verdict"] for item in three["disagreement"]}
    others = sorted(number for number, row in by_number.items()
                    if number != 3 and (row["contested"]
                                        or row["verdict"]
                                        is not PAIR_MIXED[number]))
    ok = (three["verdict"] is UNKNOWN and three["contested"]
          and "CONTESTED" in three["verdict_label"]
          and said == {MET, NOT_MET}
          and {item["source_name"] for item in three["disagreement"]} == both
          and not others)
    results.append({
        "name": "two_disagreeing_authorities_render_contested",
        "what": "a criterion two live authorities answer DIFFERENTLY renders "
                "UNKNOWN / CONTESTED, naming both files and both verdicts - "
                "and leaves the eight they agree on alone",
        "ok": ok,
        "detail": ("criterion 3 is %s off two authorities recording %s, and "
                   "the other eight are unchanged"
                   % (three["verdict_label"], sorted(said)) if ok else
                   "criterion 3 rendered %s (contested=%s) off %s, and %s "
                   "other rows moved"
                   % (three["verdict_label"], three["contested"],
                      sorted(said), others or "no"))})

    # C3. AN AUTHORITY THE CONFIGURATION DOES NOT NAME, PRESENT AND
    #     ANSWERING, MAKES THE PAGE SAY ITS SET MAY BE INCOMPLETE. Without
    #     this control the whole task ships the blindness it was written to
    #     remove: C1 and C2 are both satisfied by a page that reads exactly
    #     the files it was told about and never looks beside them.
    #
    #     The listing is injected rather than written to disk, for two
    #     reasons that are not convenience: `report()` promises to write no
    #     file, and the directory this scans is the ops estate, which this
    #     lane may not write to. The REAL `os.listdir` path is proven by
    #     `test_an_unregistered_authority_is_announced` against a real
    #     temporary directory - stated here because a control reported as
    #     passing in a form it was not run in is this lane's own B7.
    seen = _discover(
        None, PRESENT, [source["name"] for source in SOURCES],
        entries=[{"name": os.path.basename(SOURCES[0]["name"]),
                  "text": _pair_fixture(PAIR_MIXED, "A CONFIGURED FILE")},
                 {"name": "control-stranger.md",
                  "text": _pair_fixture(PAIR_MIXED, "A STRANGER")},
                 {"name": "control-silent.md",
                  "text": "# A FILE THAT ANSWERS NOTHING" + chr(10)}])
    announced = [item["name"] for item in seen["found"]]
    ok = (announced == ["control-stranger.md"]
          and seen["found"][0]["answered"] == [1, 2, 3, 4, 5, 6, 7, 8, 9]
          and seen["scanned"] == 3)
    results.append({
        "name": "an_unregistered_authority_is_announced",
        "what": "a file the configuration does not name, present and "
                "answering a criterion, makes the page say its authority "
                "set may be incomplete - and a configured file and a silent "
                "one do not",
        "ok": ok,
        "detail": ("the stranger was announced answering all nine; the "
                   "configured file and the silent one were not" if ok else
                   "the scan of 3 entries announced %s" % (announced,))})

    # C4. THE PAGE CAN STILL RENDER MET. An instrument that only ever says
    #     UNKNOWN is not cautious, it is broken - and the four rules added
    #     tonight all push towards UNKNOWN, so this is the one that proves
    #     none of them became unconditional.
    rows = _control_chain(
        [_pair_source("control-pair-a.md", PAIR_ALL_MET, 1, "PAIR A"),
         _pair_source("control-pair-b.md", PAIR_ALL_MET, 2, "PAIR B")], now)
    verdicts = {row["verdict"] for row in rows}
    verdict, _why = conjunction_of(rows, complete=True)
    ok = verdicts == {MET} and verdict is MET
    results.append({
        "name": "agreeing_authorities_can_still_render_met",
        "what": "nine criteria that every authority records MET render MET, "
                "and the conjunction over them is MET - so no rule added "
                "for the contested case became unconditional",
        "ok": ok,
        "detail": ("all %d rows MET and the conjunction MET, from two "
                   "agreeing authorities" % len(rows) if ok else
                   "two all-MET authorities produced rows %s and "
                   "conjunction %s" % (sorted(verdicts), verdict))})
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
    seen = _discover(ops, ops_state,
                     [source["name"] for source in chain])
    tally = {MET: 0, NOT_MET: 0, UNKNOWN: 0, WITHDRAWN: 0, STALE: 0}
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
        # EVERY AUTHORITY THAT COULD NOT BE READ, WITH THE PATH TRIED. The
        # designated authority failing is not the same event as a rank-3
        # lane file failing, so they are listed rather than counted - and
        # each carries the absolute path, because "the authority could not be
        # read" is useless to whoever has to go and look without it.
        "unread": [{"name": source["name"], "rank": source["rank"],
                    "state": source["state"],
                    "path": source.get("attempted_path")}
                   for source in sorted(chain, key=lambda s: s["rank"])
                   if source["state"] != PRESENT],
        # Blocks skipped because an enclosing heading called them history.
        "retained_blocks": sum(source["retained_blocks"]
                               for source in chain),
        # Sources whose only verdict block was marked history, so the page is
        # reading an appendix because there was nothing else to read.
        "retained_used": [source["name"] for source in chain
                          if source["retained"]],
        "disagreements": [row["number"] for row in rows
                          if row["disagreement"]],
        # The glossaries come from this module, so the renderer holds no
        # table of its own and cannot drift from the reader.
        "verdict_glossary": [{"label": label, "why": why}
                             for label, why in VERDICT_TEXT.values()],
        "location_glossary": [{"label": label, "why": why}
                              for label, why in LOCATION_TEXT.values()],
        "stale_seconds": STALE_SECONDS,
        # THE SET THIS PAGE USED, BY PATH, so no total below is a total over
        # something a reader cannot enumerate.
        #
        # ROOT-RELATIVE AND NOT ABSOLUTE, and the conflict is named rather
        # than quietly resolved. TASK 0090 recorded that a healthy page
        # prints no absolute path, because an absolute path is somebody's
        # home directory in a screenshot; TASK 0120's brief requires the set
        # printed by path. A path under a NAMED root satisfies both - it
        # identifies every file unambiguously and names no home directory -
        # and the absolute path is still printed for an authority that could
        # not be READ, which is 0090's own exception and the case where a
        # reader has to go and look.
        "authority_set": [
            {"name": source["name"], "rank": source["rank"],
             "state": source["state"],
             "located": _located(source, root, ops, ops_state),
             "answered": source["answered"]}
            for source in sorted(chain, key=lambda item: item["rank"])],
        # AUTHORITY-SHAPED FILES THE CONFIGURATION DOES NOT NAME. Announced,
        # never read for a verdict.
        "discovery": seen,
        "discovered": seen["found"],
        "discovery_scanned": seen["scanned"],
        "discovery_blind": seen["blind"],
        "set_may_be_incomplete": bool(seen["found"]) or seen["blind"],
    }
    data.update(_registry_check(root, ops, ops_state, now))
    # THE SENTENCE THAT IS THE WHOLE POINT. CANARY-01 activates only when all
    # nine are met, so anything other than nine MET means it does not go -
    # and an UNKNOWN is never allowed to read as a pass on the way there.
    data["all_nine_met"] = tally[MET] == len(CRITERIA)
    # AND THE CONJUNCTION ITSELF, which is not the tally and not a
    # fraction. `EXIT-NINE-AT-ONCE-2026-10-16.md` exits 2 on this
    # question; nine rows with no overall verdict is the rendering that
    # loses it.
    verdict, why = conjunction_of(
        data["rows"], complete=not data["set_may_be_incomplete"])
    data["conjunction"] = verdict
    data["conjunction_label"] = VERDICT_TEXT[verdict][0]
    data["conjunction_why"] = why
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
    # EVERY BUCKET, INCLUDING THE EMPTY ONES. A summary line that printed
    # three of five states summed to eight on a nine-row page the first time
    # a verdict was WITHDRAWN, and a tally that does not add up is how a
    # reader learns to stop reading the tally.
    out.append("  %s - all nine met: %s"
               % (", ".join("%d %s" % (data["tally"][verdict],
                                       VERDICT_TEXT[verdict][0])
                            for verdict in (MET, NOT_MET, UNKNOWN,
                                            WITHDRAWN, STALE)),
                  "YES" if data["all_nine_met"] else "NO"))
    if data["registry_drift"]:
        out.append("  DRIFT: " + data["registry_drift"])
    return "\n".join(out)


if __name__ == "__main__":                                  # pragma: no cover
    print(describe())
