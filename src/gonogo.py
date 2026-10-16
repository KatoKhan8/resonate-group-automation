#!/usr/bin/env python3
"""One question: can CANARY-01 send right now, and if not, what is the
shortest list.

## Why this exists

The operator has a runbook, an exit-criteria file, a decisions sheet, a
preflight and a 158 KB continuity file. On the morning of a first live send
he is not going to read five documents. The first line of
`CANARY-01-RUNBOOK-2026-10-16.md` is already the answer; this module is that
line kept current by READING the artifacts rather than by somebody
remembering to edit it.

## What it does NOT do, and this is the whole design

**It re-measures nothing.** Not one verdict here is produced by this module.
Every one is read out of a document another lane wrote, attributed to that
document by name, and shown with its age. Four other lanes own those
measurements and on 2026-10-16 two of them corrected each other inside twelve
hours - so a number on this page that no artifact contains is a defect, not a
feature. There is no git call, no provider call, no socket, no credential and
no write.

That makes AGE a first-class field rather than a decoration. A blocker
measured at 03:47 on a tree that has since moved is not a current verdict,
and the one way this page can mislead is by rendering an eight-hour-old
reading as though somebody had just looked. So every row carries the
measurement time the artifact itself states, what it was measured against,
and - when that time is older than `STALE_SECONDS` - the word STALE, which is
a DIFFERENT WORD from NOT MET because it leads to a different action:
re-measure, not repair.

## The verdict

`GO` only when every row reads MET, every source was read and parsed, every
control passed, and nothing is stale. Anything else is `NO_GO`. In
particular **GO is impossible while any row is UNKNOWN** - that rule is
already written into `src.exitcriteria` and this module reuses its vocabulary
rather than inventing a second one, because two vocabularies for one verdict
is how the two drift.

## Where the rows come from

    CANARY-01-RUNBOOK-2026-10-16.md     the shortest list, in its own order,
                                        and the twelve preconditions P1-P12
    EXIT-CRITERIA-2026-10-16.md         the designated exit-criteria authority,
                                        read by `src.exitcriteria`'s parser
    DECISIONS-OPEN-2026-10-16.md        TIER 2, the sheet's own name for
                                        the canary's blockers
    CANARY-01-PREFLIGHT-2026-10-16.md   whether the cohort is cleared to send

Each source is read fail-closed. Absent, unreadable, empty, or present and
holding nothing this module can parse - those are four different sentences
and none of them is MET. A source that cannot be read still produces a ROW,
carrying UNKNOWN and the reason, because a question that silently disappears
from a go/no-go screen is the worst failure this page has available to it.
"""
import datetime
import os
import re

from src import exitcriteria

# ---------------------------------------------------------------- vocabulary
#
# ONE VOCABULARY, TAKEN FROM `src.exitcriteria` RATHER THAN RESTATED. That
# module's five words already encode the rules this page has to obey - UNKNOWN
# is not a soft NOT MET, WITHDRAWN is not the value it held, STALE is not a
# verdict - and a second set of constants spelling the same words is how two
# readers come to disagree about what they mean.

MET = exitcriteria.MET
NOT_MET = exitcriteria.NOT_MET
UNKNOWN = exitcriteria.UNKNOWN
WITHDRAWN = exitcriteria.WITHDRAWN
STALE = exitcriteria.STALE

VERDICT_TEXT = exitcriteria.VERDICT_TEXT

#: Source states, same four kinds of nothing, same reasons.
UNCONFIGURED = exitcriteria.UNCONFIGURED
ABSENT = exitcriteria.ABSENT
UNREADABLE = exitcriteria.UNREADABLE
EMPTY = exitcriteria.EMPTY
NO_BLOCK = exitcriteria.NO_BLOCK
PRESENT = exitcriteria.PRESENT

#: Which clock a row's age came from.
AS_OF_STAMP = exitcriteria.AS_OF_STAMP
AS_OF_MTIME = exitcriteria.AS_OF_MTIME
AS_OF_NONE = exitcriteria.AS_OF_NONE

OPS_DIR = exitcriteria.OPS_DIR
REPO_ROOT = exitcriteria.REPO_ROOT

# ------------------------------------------------------------ the two words

GO = "go"
NO_GO = "no_go"

VERDICT_LABEL = {GO: "GO", NO_GO: "NO-GO"}

# ----------------------------------------------------------- where it lives

LOC_REPO = exitcriteria.LOC_REPO
LOC_OPS = exitcriteria.LOC_OPS
LOC_OPERATOR = exitcriteria.LOC_OPERATOR
LOC_PROVIDER = exitcriteria.LOC_PROVIDER

#: The main checkout's gitignored `work/` state. A FIFTH home, added here
#: rather than borrowed, because P9 is the live instance and none of the four
#: above describes it: `work/` is not in the repository (it is gitignored), it
#: is not in the ops estate, it is not a person and it is not a provider. It
#: is production runtime state in one directory on one machine, closed to
#: every lane by standing instruction - and the runbook's own finding is that
#: the orientation command resolves it against whichever tree you stand in,
#: so from a worktree it answers about an empty estate and reads as safe.
LOC_PRODUCTION = "production"

#: A row whose authority lives in more than one of the above. Not UNKNOWN: a
#: split home is a fact somebody measured, and `EXIT-CRITERIA-2026-10-16.md`
#: says exactly that of criterion 3 ("split, and now three-way").
LOC_SPLIT = "split"

#: The artifact names no path for this row. Also not UNKNOWN - the row's
#: VERDICT may be perfectly well established while the document simply never
#: writes down where it was read from.
LOC_UNSTATED = "unstated"

LOCATION_TEXT = dict(exitcriteria.LOCATION_TEXT)
LOCATION_TEXT[LOC_PRODUCTION] = (
    "in the main checkout's production `work/` state",
    "gitignored, on one machine, and closed to every lane by standing "
    "instruction. It cannot be read from a worktree at all: the command "
    "resolves `work/` against the tree it is run in, so from here it answers "
    "about an empty estate and returns a reassuring False")
LOCATION_TEXT[LOC_SPLIT] = (
    "split across more than one home",
    "the artifact names authorities in two or more different places for this "
    "one row. Stated rather than resolved - a reader who has to go and look "
    "needs both")
LOCATION_TEXT[LOC_UNSTATED] = (
    "not stated by the artifact",
    "the document records a verdict for this row and never writes down where "
    "it was read from. That is a gap in the artifact, not a verdict about "
    "the row")

# ------------------------------------------------------------- who fixes it

OWNER_CONSTRUCTION = "construction"
OWNER_OPERATOR = "operator"
OWNER_UNSTATED = "unstated"

OWNER_TEXT = {
    OWNER_CONSTRUCTION: (
        "construction",
        "code, a test or a merge. Needs nobody's permission and no lane has "
        "to wait for an answer to start it"),
    OWNER_OPERATOR: (
        "operator",
        "a sentence only the operator can say, a command only he can run, or "
        "a gate only he may change. No amount of construction closes it"),
    OWNER_UNSTATED: (
        "not stated",
        "no artifact this page reads says which of the two this row is. NOT "
        "a reason to treat it as construction: an unowned blocker is how a "
        "row sits untouched for a day while each side assumes the other has "
        "it"),
}

# ------------------------------------------------------------ the staleness
#
# SIX HOURS, and the justification is this estate's own measured correction
# interval rather than a round number.
#
# What the artifacts show about how fast a verdict here goes wrong:
#
#   * the runbook was written at 02:52-03:02 and REWRITTEN at 03:45-03:58
#     because two lanes landed work in between. FOUR of its verdicts changed
#     in fifty-six minutes.
#   * `DECISIONS-OPEN-2026-10-16.md` item 8 was VOIDED at 08:57:16, "forty
#     minutes after this question was last put to you".
#   * that same sheet was appended to at 09:58 and again at 10:55.
#
# So the interval at which a verdict in this estate is superseded is well
# under an hour, and ANY threshold is generous. Six is chosen because it is
# the span over which this estate has, measurably, produced a document that
# supersedes the one being read: the runbook's 03:58 claim about criterion 6
# was void by 08:57, five hours later. A twenty-four-hour threshold - which
# `src.exitcriteria` uses correctly for its own question - would have called
# that runbook fresh all day.
#
# It is deliberately NOT configurable. A threshold on a safety screen that
# can be widened to make a row stop complaining is the same defect as
# widening a lint rule to make a draft pass.
STALE_SECONDS = 6 * 3600

# ---------------------------------------------------------------- the sources

RUNBOOK = "CANARY-01-RUNBOOK-2026-10-16.md"
EXIT_CRITERIA = "EXIT-CRITERIA-2026-10-16.md"
DECISIONS = "DECISIONS-OPEN-2026-10-16.md"
PREFLIGHT = "CANARY-01-PREFLIGHT-2026-10-16.md"

#: The four, in the order they are read and rendered. `answers` is the
#: question each one owns, and it is load-bearing: when a source cannot be
#: read, this sentence is what the UNKNOWN row is ABOUT. Without it an
#: unreadable source would contribute no row at all, and a question that
#: vanishes from a go/no-go screen is indistinguishable from a question that
#: was answered yes.
#:
#: There is no `rank` here and that is deliberate. These four answer
#: DIFFERENT questions - they are not four readings of one. Where two of them
#: do speak to the same question, they are rendered as a dispute and the row
#: goes UNKNOWN; rank would let this page pick a winner, which is the
#: operator's sentence to write and not a page's.
SOURCES = (
    {"key": "runbook", "name": RUNBOOK, "where": LOC_OPS, "reader": "runbook",
     "answers": "whether the canary can send today, the ordered shortest "
                "list of what would change that, and the twelve "
                "preconditions behind it"},
    {"key": "preflight", "name": PREFLIGHT, "where": LOC_OPS,
     "reader": "preflight",
     "answers": "whether the 23 cohort contacts are cleared to be sent to, "
                "one row per contact against 22 suppression rules"},
    {"key": "exit", "name": EXIT_CRITERIA, "where": LOC_OPS,
     "reader": "exit_criteria",
     "answers": "the designated re-audit of the CANARY-01 exit criteria, "
                "which activates only when all nine are MET"},
    {"key": "decisions", "name": DECISIONS, "where": LOC_OPS,
     "reader": "decisions",
     "answers": "which open decisions are the canary's own blockers, and "
                "which of them a lane cannot close"},
)

# ----------------------------------------------------------- reading verdicts
#
# The phrases, longest first, and NOTHING ELSE IS ACCEPTED. `NOT MET` has to
# be tried before `MET` or every refusal in these documents reads as a pass -
# which is not hypothetical, it is one regex ordering away.

_VERDICT_PHRASE = (
    ("NOT MET", NOT_MET),
    ("MET", MET),
    ("UNKNOWN", UNKNOWN),
)

#: Words an artifact uses to take a verdict back. Same four as
#: `src.exitcriteria`, because they are the four this estate actually writes.
_WITHDRAWN_WORD = re.compile(r"\b(VOID|WITHDRAWN|SUPERSEDED|REVOKED)\b")

#: A struck-through span. A heading whose TITLE is struck is a withdrawn item
#: however triumphant the words inside the strike.
_STRUCK = re.compile(r"~~(.+?)~~", re.S)


def verdict_phrase(text):
    """The verdict a phrase records, and never a guess.

    Returns `(verdict, raw)`. A phrase this reader does not recognise comes
    back UNKNOWN with the raw text kept, which is the whole fail-closed
    contract: `NOT ANSWERABLE FROM HERE` and `CANNOT BE ANSWERED FROM HERE`
    both appear in the runbook and neither is one of the three words above,
    so both are UNKNOWN - not MET, and not silently dropped either.
    """
    raw = " ".join((text or "").split())
    if not raw:
        return UNKNOWN, None
    upper = raw.upper()
    for phrase, verdict in _VERDICT_PHRASE:
        if upper == phrase or upper.startswith(phrase + " ") \
                or upper.startswith(phrase + ".") \
                or upper.startswith(phrase + ",") \
                or upper.startswith(phrase + "\u2014") \
                or upper.startswith(phrase + " \u2014"):
            return verdict, raw
    return UNKNOWN, raw


# ---------------------------------------------------------- redacting a home
#
# A screen is screenshotted. An absolute path under `C:\Users\<name>` is
# somebody's full name on that screenshot, and these artifacts are full of
# them - `C:\Users\Zvonimir\Desktop\resonate-ops\STOP-SENDING` is a
# precondition's authority. `src.exitcriteria` states the rule and keeps one
# exception, an authority that could not be READ, because a reader who has to
# go and look needs the path. This module keeps the rule and does not need
# the exception: every path it publishes goes through here first.

_HOME = re.compile(r"[A-Za-z]:[\\/]Users[\\/][^\\/\s]+", re.I)

#: The three directory names this estate's own documents use. A path is cut
#: back to whichever of them it contains, so `resonate-ops\STOP-SENDING`
#: survives intact and the four segments above it do not.
_ANCHORS = ("resonate-ops", "resonate-trees", "resonate-group-automation")


def safe_path(text):
    """An artifact's path with the home directory taken off it."""
    if not text:
        return text
    out = text
    for anchor in _ANCHORS:
        index = out.find(anchor)
        if index > 0 and _HOME.match(out[:index] or ""):
            out = out[index:]
            break
    return _HOME.sub("<home>", out)


def redact(text):
    """Free prose with any home directory in it replaced.

    Applied to every statement and reason this module publishes, not only to
    the things it has classified as paths - a sentence quoting a path is just
    as readable in a screenshot as a path in a path column.
    """
    if not text:
        return text
    return _HOME.sub("<home>", text)


# ------------------------------------------------------------ finding a home
#
# WHERE an authority lives, decided per PATH and never per row. Each path is
# classified on its own evidence and the deciding substring is published with
# it, so the classification is checkable rather than asserted. A row whose
# paths disagree is SPLIT, which is a fact; a row with no path at all is
# UNSTATED, which is a gap in the artifact. Neither is allowed to become a
# verdict about the row.

#: What makes a backticked span a path rather than an identifier. Without
#: this, `` `APPROVED` ``, `` `sending.live` `` and `` `STOP-SENDING` `` all
#: arrive as paths and the location column fills up with nonsense.
_LOOKS_LIKE_PATH = re.compile(
    r"[\\/]|\.(?:md|py|json|csv|ya?ml|txt|jsonl|sh|ps1)$", re.I)

#: A provider endpoint, which is a home and not a path. The path part stops at
#: a backtick as well as at whitespace: these documents write endpoints inside
#: code spans, and `\S+` swallowed the closing backtick into the endpoint.
_ENDPOINT = re.compile(r"\b(?:GET|POST|PUT|PATCH|DELETE)\s+/[^\s`]+")


def _home_of(path):
    """Which of the five homes a single path names, and what decided it."""
    low = path.lower().replace("\\", "/")
    if "resonate-ops" in low:
        return LOC_OPS, "resonate-ops"
    if low.startswith("work/") or "/work/" in low:
        return LOC_PRODUCTION, "work/"
    for prefix in ("src/", "scripts/", "tests/", "config/", "docs/",
                   "canary/", "tools/"):
        if low.startswith(prefix) or ("/" + prefix) in low:
            return LOC_REPO, prefix
    return None, None


def homes_in(text):
    """Every authority home the text names, with the path that said so.

    Deduplicated on the published path, so a document repeating a filename
    four times does not make a row look four times as well attested.
    """
    found = []
    seen = set()
    for raw in re.findall(r"`([^`\n]+)`", text or ""):
        candidate = raw.strip()
        if not candidate or not _LOOKS_LIKE_PATH.search(candidate):
            continue
        where, marker = _home_of(candidate)
        if where is None:
            continue
        shown = safe_path(candidate)
        if shown in seen:
            continue
        seen.add(shown)
        found.append({"path": shown, "where": where, "marker": marker})
    for endpoint in _ENDPOINT.findall(text or ""):
        shown = " ".join(endpoint.split())
        if shown in seen:
            continue
        seen.add(shown)
        found.append({"path": shown, "where": LOC_PROVIDER,
                      "marker": "an HTTP verb and a path"})
    return found


def located(homes):
    """One word for a row's home: the agreed one, SPLIT, or UNSTATED."""
    kinds = {home["where"] for home in homes}
    if not kinds:
        return LOC_UNSTATED
    if len(kinds) == 1:
        return kinds.pop()
    return LOC_SPLIT


# ------------------------------------------------------------------- the age

#: `2026-10-16 03:47:54`, with or without the seconds. The documents write
#: their clock in four shapes and these are the two that carry a time.
_CLOCK = re.compile(r"(\d{4}-\d{2}-\d{2})[ T](\d{2}):(\d{2})(?::(\d{2}))?")

#: A bare date, for a document that stamps a day and no hour.
_DAY = re.compile(r"(?<![-\w])(\d{4}-\d{2}-\d{2})(?![-\w])")

#: `*Measured: `suppression/0320` 08:35, ...*` - a time of day inside one
#: item, which is that item's own measurement time rather than the
#: document's. A decisions sheet appended to at 10:55 does not make an item
#: measured at 08:35 fresher than it is.
_ITEM_CLOCK = re.compile(r"(\d{1,2}):(\d{2})(?::(\d{2}))?\b")


#: How many lines at the head of a document its own stamp may be read from,
#: and how many a SHA may be. BOUNDED, AND THE BOUND IS THE POINT: the first
#: version of this reader took the latest `YYYY-MM-DD HH:MM` anywhere in the
#: text, which on the 107 KB preflight meant "the newest timestamp this
#: document mentions" rather than "when this document was measured" - it aged
#: the preflight at 11h11m from a clock buried in a per-contact row. A
#: document's own provenance is in its first page; anything further down is
#: evidence about something else.
HEAD_LINES = 40

#: The same bound for SHAs. A 1,000-line artifact quoting other lanes' commits
#: would otherwise have this page reporting one of those as what the verdict
#: was measured against.
HEAD_LINES_SHA = 80


def head(text, lines=HEAD_LINES):
    """The first `lines` lines of a document."""
    return "\n".join((text or "").splitlines()[:lines])


def _stamp_with_time(text):
    """The document's own clock, as a datetime, or None.

    The LATEST one in the text it was given, not the first: these documents
    open with a title date and then state the batch clock, and the batch
    clock is the measurement. Callers bound the text they pass in - see
    `HEAD_LINES`.
    """
    best = None
    for match in _CLOCK.finditer(text or ""):
        try:
            when = datetime.datetime.strptime(
                "%s %s:%s:%s" % (match.group(1), match.group(2),
                                 match.group(3), match.group(4) or "00"),
                "%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
        if best is None or when > best:
            best = when
    return best


def age_of(when, kind, now):
    """How old a reading is, and whether that makes it STALE.

    Never the render's clock standing in for the measurement's. A reading
    with no establishable time is not fresh and is not old either: it is
    `age_seconds: None`, and this page treats that as STALE, because an
    undated verdict on the morning of a first live send is a memory.
    """
    if when is None:
        return {"as_of": None, "as_of_kind": AS_OF_NONE, "age_seconds": None,
                "age_label": "no measurement time could be established",
                "in_future": False, "stale": True}
    label = when.replace(microsecond=0).isoformat(" ")
    age = int((now - when).total_seconds())
    if age < 0:
        # A stamp ahead of the clock. Its own condition: one of the two is
        # wrong and this page cannot say which, so it is not called fresh.
        return {"as_of": label, "as_of_kind": kind, "age_seconds": None,
                "age_label": "stamped in the future, which this page cannot "
                             "resolve",
                "in_future": True, "stale": True}
    return {"as_of": label, "as_of_kind": kind, "age_seconds": age,
            "age_label": humanise(age), "in_future": False,
            "stale": age > STALE_SECONDS}


def humanise(seconds):
    """`7h 43m`. Minutes matter here: four verdicts changed in fifty-six."""
    if seconds is None:
        return "unknown"
    if seconds < 60:
        return "%ds" % seconds
    minutes, _ = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if not hours:
        return "%dm" % minutes
    return "%dh %02dm" % (hours, minutes)


# ------------------------------------------- what it was measured against


def measured_against(text):
    """The SHAs and trees the artifact says it measured at.

    Read, never checked. Verifying that `origin/master` is still
    `b1f290c84` would be a git call, which is a measurement, which is the one
    thing this module does not do. What it CAN do honestly is show the reader
    which commit a verdict belongs to, so a verdict against a tree that has
    moved is visibly a verdict against a tree that has moved.
    """
    out = {"origin_master": None, "trees": [], "shas": []}
    match = re.search(r"origin/master\s*=?\s*`?([0-9a-f]{7,40})`?", text or "")
    if match:
        out["origin_master"] = match.group(1)
    for tree in re.finditer(
            r"(wt-[a-z0-9-]+)[`\s,]+.{0,24}?`?([0-9a-f]{9,40})`?", text or ""):
        entry = {"name": tree.group(1), "sha": tree.group(2)}
        if entry not in out["trees"]:
            out["trees"].append(entry)
    for sha in re.findall(r"`([0-9a-f]{9,40})`", text or ""):
        if sha != out["origin_master"] and sha not in out["shas"]:
            out["shas"].append(sha)
    return out


def _stated_clock(text, lines=HEAD_LINES):
    """When a document says it was measured, from its own first page.

    Returns the `{"when", "kind"}` shape the chain expects, or None - and
    None is the honest answer rather than a fallback, because the caller then
    uses the file's modification time and LABELS it as such. The two are
    different claims: `03:47:54` is when somebody ran a command, and an mtime
    is when the bytes were last touched, which can be a typo fix.
    """
    when = _stamp_with_time(head(text, lines))
    return {"when": when, "kind": AS_OF_STAMP} if when else None


def against_label(against):
    """The one-line form of the above, for a table cell."""
    parts = []
    if against.get("origin_master"):
        parts.append("origin/master " + against["origin_master"][:9])
    for tree in against.get("trees", [])[:3]:
        parts.append("%s %s" % (tree["name"], tree["sha"][:9]))
    if not parts:
        for sha in against.get("shas", [])[:2]:
            parts.append(sha[:9])
    # ASCII. This string is printed to a Windows console as well as to a
    # browser, and the console here is cp1250: a middle dot came back as a
    # replacement character in the terminal render.
    return " | ".join(parts) or None


# -------------------------------------------------------- cross-source joins

#: `criterion 6`, `criteria 3`, `criterion-3`. The one key both the runbook
#: and the decisions sheet use for the same question, which is what makes a
#: cross-document dispute detectable without a hand-written mapping between
#: the two documents' item numbers.
_CRITERION_REF = re.compile(r"criteri(?:on|a)[\s\-]*(\d)\b", re.I)

#: `P3`, `P10`. The runbook's own reference from an item in the shortest list
#: down to the precondition that measured it.
_P_REF = re.compile(r"\bP(\d{1,2})\b")


def criteria_refs(text):
    return sorted({int(n) for n in _CRITERION_REF.findall(text or "")})


def p_refs(text):
    return sorted({int(n) for n in _P_REF.findall(text or "")})


# =========================================================== the four readers
#
# Each takes TEXT and returns a dict. None of them raises: a document that
# does not parse comes back with `rows: []` and a `why` naming what was
# looked for and not found, which is what makes the source NO_BLOCK and its
# question UNKNOWN. A reader that threw would take the whole page down, and a
# go/no-go screen that 500s is a screen that gets skipped.


def read_runbook(text):
    """The headline, the shortest list, and the twelve preconditions."""
    lines = (text or "").splitlines()
    out = {"rows": [], "why": None, "headline": None, "headline_verdict": None,
           "shortest": [], "owners": {}, "clock": None, "against": {}}

    # The headline. A top-level heading that opens with YES or NO - which is
    # the shape the runbook actually uses - and nothing else is accepted. The
    # page does NOT take its verdict from this line; it takes it from the
    # rows and then checks this line against it, because a document's own
    # summary and its own table have disagreed in this estate before.
    for line in lines[:40]:
        match = re.match(r"^#{1,2}\s+(NO|YES)\b[.,:]?\s*(.*)$", line.strip())
        if match:
            out["headline"] = redact(line.strip().lstrip("# ").strip())
            out["headline_verdict"] = (
                NO_GO if match.group(1).upper() == "NO" else GO)
            break

    out["clock"] = _batch_clock(text) or _stated_clock(text)
    out["against"] = measured_against(head(text, HEAD_LINES_SHA))

    preconditions = _preconditions(lines)
    out["rows"] = preconditions
    out["shortest"] = _shortest_list(lines)
    out["owners"] = _owner_split(text)
    if not preconditions and not out["shortest"]:
        out["why"] = ("read in full and it holds neither a `P<n>` "
                      "precondition table nor a numbered shortest list under "
                      "a line naming one, so there is nothing in it this "
                      "page can turn into a row")
    return out


def _batch_clock(text):
    """The runbook's stated batch clock - one real clock for twelve rows.

    Taken from the `batch clock   local ...` line specifically and not from
    the newest timestamp in the document, because the document is full of
    per-measurement times and the batch clock is the one it promises all
    twelve rows were read under.
    """
    match = re.search(r"batch clock\s+local\s+([^\n]+)", text or "")
    if match:
        when = _stamp_with_time(match.group(1))
        if when:
            return {"when": when, "kind": AS_OF_STAMP}
    # The written/second-dispatch stamp, which is the next most specific
    # thing the document says about when it was produced.
    match = re.search(r"^\s*written\s+([^\n]+)$", text or "", re.M)
    if match:
        when = _stamp_with_time(match.group(1))
        if when:
            return {"when": when, "kind": AS_OF_STAMP}
    return None


def _preconditions(lines):
    """P1-P12, read TWICE from one document, and the two readings compared.

    The compact table in section 2 and the `### P<n>` heading below it are two
    independent statements of the same verdict. Reading only one would be
    cheaper and would also mean a document whose summary and whose detail
    disagree renders whichever this page happened to parse. They are compared
    instead, and a disagreement is UNKNOWN - the same rule
    `src.exitcriteria` applies across two files, applied here inside one.
    """
    table = {}
    for line in lines:
        # `(?=[ \t]|$)` and not `(?=[ \t])`: a row reduced to `P4` with
        # nothing after it has to be SEEN and reported as having no verdict
        # column. A lookahead demanding a space makes that row invisible,
        # which is the one direction a precondition reader may not fail in.
        match = re.match(r"^ {2,}P(\d{1,2})(?=[ \t]|$)(.*)$", line.rstrip())
        if not match:
            continue
        number = int(match.group(1))
        rest = match.group(2)
        note = None
        trailing = re.search(r"\s{2,}\(([^)]*)\)\s*$", rest)
        if trailing:
            note = trailing.group(1)
            rest = rest[:trailing.start()]
        parts = [part for part in re.split(r"\s{2,}", rest.strip()) if part]
        if len(parts) < 2:
            table[number] = {"statement": redact(rest.strip()) or None,
                             "verdict": UNKNOWN, "raw": None, "note": note,
                             "why": "its row in the precondition table has no "
                                    "verdict column this page could separate "
                                    "from the claim"}
            continue
        verdict, raw = verdict_phrase(parts[-1])
        table[number] = {"statement": redact(" ".join(parts[:-1])),
                         "verdict": verdict, "raw": raw, "note": note,
                         "why": None}

    headings = {}
    for index, line in enumerate(lines):
        match = re.match(r"^#{3}\s+P(\d{1,2})\b\s*[\u2014\u2013-]?\s*(.*)$",
                         line.strip())
        if not match:
            continue
        number = int(match.group(1))
        tail = match.group(2)
        verdict, raw = UNKNOWN, None
        spans = re.findall(r"\*\*(.+?)\*\*", tail)
        for span in spans:
            candidate, candidate_raw = verdict_phrase(span)
            if candidate_raw is not None and candidate != UNKNOWN:
                verdict, raw = candidate, candidate_raw
                break
        else:
            if spans:
                # A bold span that is not one of the three words. UNKNOWN,
                # and the words kept: `CANNOT BE ANSWERED FROM HERE` is a
                # real verdict in this document and dropping it would leave
                # the row looking unmeasured rather than unanswerable.
                verdict, raw = UNKNOWN, " ".join(spans[0].split())
        statement = re.sub(r"\*\*(.+?)\*\*", "", tail)
        headings[number] = {
            "statement": redact(statement.strip(" .\u2014-")) or None,
            "verdict": verdict, "raw": raw,
            "body": "\n".join(_section_body(lines, index)),
        }

    rows = []
    for number in sorted(set(table) | set(headings)):
        first = table.get(number)
        second = headings.get(number)
        body = (second or {}).get("body", "")
        statement = ((first or {}).get("statement")
                     or (second or {}).get("statement"))
        row = {"number": number, "statement": statement,
               "table_verdict": (first or {}).get("verdict"),
               "heading_verdict": (second or {}).get("verdict"),
               "table_raw": (first or {}).get("raw"),
               "heading_raw": (second or {}).get("raw"),
               "note": (first or {}).get("note"),
               "body": body, "why": (first or {}).get("why")}
        if first is None:
            row["verdict"] = second["verdict"]
            row["why"] = ("only the `### P%d` section records this row; the "
                          "precondition table does not list it" % number)
        elif second is None:
            row["verdict"] = first["verdict"]
            row["why"] = ("only the precondition table records this row; "
                          "there is no `### P%d` section for it" % number)
        elif first["verdict"] == second["verdict"]:
            row["verdict"] = first["verdict"]
        else:
            row["verdict"] = UNKNOWN
            row["disagreement"] = True
            row["why"] = (
                "the runbook states this row twice and the two do not agree: "
                "its precondition table says %s and its `### P%d` section "
                "says %s. Two readings of one document, so UNKNOWN - this "
                "page does not pick which half of a document to believe"
                % (VERDICT_TEXT[first["verdict"]][0], number,
                   VERDICT_TEXT[second["verdict"]][0]))
        rows.append(row)
    return rows


def _section_body(lines, index):
    """The lines under a heading, up to the next heading of any depth."""
    body = []
    for line in lines[index + 1:]:
        if re.match(r"^#{1,6}\s", line):
            break
        body.append(line)
    return body


def _shortest_list(lines):
    """The ordered items under the line that promises them.

    Keyed on the phrase the runbook writes - "the shortest list of things
    that would change that" - because the whole point of this page is that
    line, and an items list found anywhere else in a 44 KB document is some
    other list.
    """
    start = None
    for index, line in enumerate(lines[:60]):
        if "shortest list" in line.lower():
            start = index + 1
            break
    if start is None:
        return []
    items = []
    current = None
    for line in lines[start:start + 80]:
        match = re.match(r"^(\d{1,2})\.\s+(.*)$", line)
        if match:
            if current:
                items.append(current)
            current = {"number": int(match.group(1)),
                       "text": match.group(2).strip()}
            continue
        if current is None:
            if line.strip():
                continue
            continue
        if line.startswith("   ") and line.strip():
            current["text"] += " " + line.strip()
            continue
        if not line.strip():
            continue
        break
    if current:
        items.append(current)
    out = []
    for item in items:
        text = " ".join(item["text"].split())
        lead = re.match(r"^\*\*(.+?)\*\*", text)
        out.append({"number": item["number"],
                    "text": redact(text),
                    "lead": redact(lead.group(1).strip(" .")) if lead
                            else redact(text.split(".")[0]),
                    "p_refs": p_refs(text),
                    "criteria": criteria_refs(text)})
    return out


def _owner_split(text):
    """The runbook's own sentence about who owns which item.

    `Items 2, 3 and 4 are construction ... Items 1, 5 and 6 are yours.` An
    item in neither list is UNSTATED and never defaulted to construction: an
    unowned blocker is how a row sits still for a day with each side assuming
    the other has it.
    """
    owners = {}
    for pattern, owner in (
            (r"Items?\s+([\d,\sand]+?)\s+(?:are|is)\s+construction",
             OWNER_CONSTRUCTION),
            (r"Items?\s+([\d,\sand]+?)\s+(?:are|is)\s+yours",
             OWNER_OPERATOR)):
        for match in re.finditer(pattern, text or "", re.I):
            for number in re.findall(r"\d+", match.group(1)):
                owners[int(number)] = owner
    return owners


def read_preflight(text):
    """Whether the cohort is cleared. Four counts, and all four required."""
    out = {"rows": [], "why": None, "counts": {}, "clock": None,
           "against": {}, "steps": [], "headline": None}
    wanted = {"assessed": r"contacts assessed",
              "cleared": r"cleared",
              "excluded": r"excluded",
              "not_cleared": r"NOT CLEARED because UNKNOWN"}
    counts = {}
    for key, label in wanted.items():
        match = re.search(r"^ {2,}%s\s{2,}(\d+)\b" % label, text or "",
                          re.M)
        if match:
            counts[key] = int(match.group(1))
    out["counts"] = counts
    missing = [key for key in wanted if key not in counts]
    out["against"] = measured_against(head(text, HEAD_LINES_SHA))
    # The preflight writes `Measured 2026-10-16 in \`wt-...\`` - a DAY and no
    # hour. So its stated clock is usually None and the chain falls back to
    # the file's mtime, labelled as an mtime. That is the honest answer: a
    # date with no time cannot establish freshness to six hours, and this
    # page must not borrow a time from somewhere else in the document to
    # cover the gap.
    out["clock"] = _stated_clock(text)
    for line in (text or "").splitlines()[:12]:
        if "NOT CLEARED" in line or "CLEARED TO SEND" in line:
            out["headline"] = redact(line.strip().strip("*"))
            break
    out["steps"] = _numbered_items(text or "",
                                   "WHAT WOULD CLEAR THE COHORT")
    if missing:
        out["why"] = ("read in full and %d of the four counts it is read for "
                      "are not in it (%s), so this page cannot say what the "
                      "cohort's clearance is"
                      % (len(missing), ", ".join(sorted(missing))))
        return out

    # THE VERDICT IS THE COUNTS, AND THE ORDER OF THESE TESTS IS THE RULE.
    # `NOT CLEARED because UNKNOWN` is checked FIRST, before any arithmetic
    # that could make 23 of 23 look like a pass. The preflight's own headline
    # says it: UNKNOWN is not a pass.
    if counts["not_cleared"] > 0:
        verdict = UNKNOWN
        why = ("%d of %d contacts are NOT CLEARED because at least one "
               "suppression rule could not be asked at all. The preflight's "
               "own sentence: UNKNOWN is not a pass"
               % (counts["not_cleared"], counts["assessed"]))
    elif counts["assessed"] == 0:
        verdict = UNKNOWN
        why = ("no contact was assessed at all. A clearance over an empty "
               "cohort is not a clearance")
    elif counts["excluded"] > 0:
        verdict = NOT_MET
        why = ("%d of %d contacts are EXCLUDED, so the cohort as recorded "
               "cannot be sent to as it stands"
               % (counts["excluded"], counts["assessed"]))
    elif counts["cleared"] == counts["assessed"]:
        verdict = MET
        why = ("all %d assessed contacts are cleared, none excluded and none "
               "left UNKNOWN" % counts["assessed"])
    else:
        verdict = UNKNOWN
        why = ("the four counts do not account for each other: %d assessed, "
               "%d cleared, %d excluded, %d not cleared"
               % (counts["assessed"], counts["cleared"], counts["excluded"],
                  counts["not_cleared"]))
    out["rows"] = [{"key": "cohort",
                    "question": "the cohort is cleared to be sent to",
                    "verdict": verdict, "why": why,
                    "body": text or ""}]
    return out


def read_decisions(text):
    """TIER 2 - the sheet's own name for the canary's blockers.

    Keyed on that heading. Every other tier on this sheet is real work and
    none of it is a canary blocker, so a page that read all nineteen items
    would bury the four that matter under fifteen that do not.
    """
    out = {"rows": [], "why": None, "clock": None, "against": {},
           "void": [], "unread_sections": [], "items_seen": 0}
    lines = (text or "").splitlines()
    out["clock"] = _stated_clock(text, 5)
    out["against"] = measured_against(head(text, HEAD_LINES_SHA))

    # EVERY numbered item, anywhere on the sheet, for the withdrawal scan.
    # A VOID item is how this sheet says a question the runbook still lists
    # has been closed, and that cross-document fact is the single most
    # valuable thing on this page.
    tier = None
    tier_note = {}
    for index, line in enumerate(lines):
        stripped = line.strip()
        tier_match = re.match(
            r"^##\s+(TIER\s+\d)\b\s*[\u2014\u2013-]?\s*(.*)$", stripped)
        if tier_match:
            tier = tier_match.group(1).upper().replace("  ", " ")
            tier_note[tier] = {
                "label": redact(stripped.lstrip("# ")),
                "body": "\n".join(_section_body(lines, index)),
            }
            continue
        item = re.match(r"^###\s+(\d{1,2})\.\s+(.*)$", stripped)
        if not item:
            if re.match(r"^##\s+(?!TIER)", stripped):
                out["unread_sections"].append(redact(stripped.lstrip("# ")))
                tier = None
            continue
        out["items_seen"] += 1
        number = int(item.group(1))
        title = item.group(2).strip()
        body = "\n".join(_section_body(lines, index))
        struck = _STRUCK.search(title)
        withdrawn_word = _WITHDRAWN_WORD.search(title)
        entry = {"number": number, "title": redact(title),
                 "plain": redact(_STRUCK.sub(r"\1", title)),
                 "tier": tier, "body": body,
                 "criteria": criteria_refs(title + " " + body),
                 "struck": bool(struck),
                 "withdrawn_word": (withdrawn_word.group(1)
                                    if withdrawn_word else None)}
        if entry["struck"] or entry["withdrawn_word"]:
            out["void"].append(entry)
        if tier == "TIER 2":
            out["rows"].append(entry)

    note = tier_note.get("TIER 2", {})
    body = note.get("body", "")
    # The sheet's own sentence about who can close these. Read rather than
    # assumed, and BOTH of its forms are matched: the live sheet writes
    # "**None of these can be closed by a lane.**", which a pattern looking
    # for "cannot be closed by a lane" misses completely - and missing it
    # silently moved two of the four blockers from `operator` to `not
    # stated`, which is the wrong direction for a column whose whole job is
    # to tell the operator which rows are waiting on him.
    lane_sentence = bool(re.search(
        r"(?:cannot be closed by a lane"
        r"|none of these\s+can be closed by a lane)", body, re.I))
    for row in out["rows"]:
        if row["struck"] or row["withdrawn_word"]:
            row["verdict"] = WITHDRAWN
            row["why"] = ("the sheet records this item as %s, so it is no "
                          "longer a blocker and is not a pass either"
                          % (row["withdrawn_word"] or "struck through"))
        else:
            row["verdict"] = NOT_MET
            row["why"] = ("an open item in the sheet's own TIER 2, \"the "
                          "canary's own four blockers\". Open means "
                          "outstanding; this page reads that, it does not "
                          "measure it")
        if lane_sentence or re.search(r"\*\*You do:\*\*", row["body"]):
            row["owner"] = OWNER_OPERATOR
        else:
            row["owner"] = OWNER_UNSTATED
        row["clock"] = _item_clock(row["body"], out["clock"])
    if "TIER 2" not in tier_note:
        out["why"] = ("read in full and it has no `## TIER 2` heading, which "
                      "is the section this page reads for the canary's own "
                      "blockers. %d numbered items were found and none of "
                      "them could be attributed to that tier"
                      % out["items_seen"])
        out["rows"] = []
    elif not out["rows"]:
        # AN EMPTY TIER 2 IS THE CLEARED STATE, AND IT HAS TO BE DISTINGUISHED
        # FROM A READER THAT HAS STOPPED WORKING. The two look identical from
        # inside this function: zero rows.
        #
        # The discriminator is measured rather than assumed: if the sheet
        # holds numbered items ANYWHERE, this reader's item pattern
        # demonstrably still matches what the sheet writes, so TIER 2 holding
        # none of them is a fact about TIER 2. If the sheet holds no numbered
        # item at all, the pattern may simply have stopped matching, and that
        # is UNKNOWN - which is `rows: []`, which makes the source NO_BLOCK
        # and its question UNKNOWN.
        if out["items_seen"]:
            out["rows"] = [{
                "number": 0,
                "title": "no open TIER 2 decision blocks the canary",
                "plain": "no open TIER 2 decision blocks the canary",
                "tier": "TIER 2", "body": body, "criteria": [],
                "struck": False, "withdrawn_word": None,
                "verdict": MET,
                "why": ("the sheet's `## TIER 2` section - its own name for "
                        "the canary's blockers - holds no numbered item, and "
                        "%d numbered items elsewhere on the sheet show this "
                        "reader's pattern still matches what the sheet "
                        "writes. An empty section and a broken reader are "
                        "the same zero, so the second is ruled out by "
                        "measurement" % out["items_seen"]),
                "owner": OWNER_OPERATOR if lane_sentence else OWNER_UNSTATED,
                "clock": out["clock"],
            }]
        else:
            out["why"] = (
                "its `## TIER 2` section holds no numbered items AND neither "
                "does any other section, so this page cannot tell an empty "
                "tier from an item format it no longer recognises. UNKNOWN, "
                "not empty")
    return out


def _item_clock(body, fallback):
    """An item's own `*Measured: ... 08:35*` time, or the sheet's.

    The sheet's header date supplies the day; the item supplies the hour.
    Without this an item measured at 08:35 would inherit the time the sheet
    was last appended to, which is 10:55, and read two hours fresher than it
    is.
    """
    if not fallback or not fallback.get("when"):
        return fallback
    match = re.search(r"\*Measured:([^*]*)\*", body or "")
    if not match:
        return fallback
    times = _ITEM_CLOCK.findall(match.group(1))
    if not times:
        return fallback
    best = None
    for hour, minute, second in times:
        try:
            when = fallback["when"].replace(
                hour=int(hour), minute=int(minute), second=int(second or 0),
                microsecond=0)
        except ValueError:
            continue
        if best is None or when > best:
            best = when
    if best is None:
        return fallback
    return {"when": best, "kind": AS_OF_STAMP}


def read_exit_criteria(text):
    """The designated exit-criteria authority, through its own parser.

    `src.exitcriteria.verdicts_from_text` and `conjunction_of` do this
    already, and they encode rules this page must not weaken: a withdrawn
    verdict never renders as the value it held, an undated one is STALE
    rather than MET, and - the one section 4 of the brief names - UNKNOWN
    never becomes a pass. Re-implementing any of that here would be a second
    authority on the same question, which is the defect this estate is named
    for.
    """
    out = {"rows": [], "why": None, "clock": None, "against": {},
           "criteria": [], "answered": []}
    parsed = exitcriteria.verdicts_from_text(text or "",
                                             self_name=EXIT_CRITERIA)
    out["against"] = measured_against(head(text, HEAD_LINES_SHA))
    out["clock"] = _stated_clock(text)
    found = parsed.get("rows") or {}
    if not found:
        out["why"] = ("read in full by `src.exitcriteria`'s own parser and it "
                      "holds no verdict block, so it answers none of the "
                      "nine")
        return out
    out["answered"] = sorted(found)
    rows = []
    for number in sorted(found):
        entry = found[number]
        verdict = entry["verdict"] if isinstance(entry, dict) else entry
        rows.append({"number": number, "verdict": verdict})
    out["criteria"] = rows
    # The conjunction over the nine, from `src.exitcriteria`, with the rows
    # this one file answers. It returns UNKNOWN when the set is short of nine
    # - which is correct and is the live case: this file re-audited 3, 5 and
    # 9 only, so it cannot settle the conjunction and must not look as if it
    # did.
    verdict, why = exitcriteria.conjunction_of(
        [{"number": row["number"], "verdict": row["verdict"],
          "disagreement": False} for row in rows])
    out["rows"] = [{
        "key": "nine",
        "question": "all nine CANARY-01 exit criteria are MET",
        "verdict": verdict if verdict in (MET, NOT_MET, UNKNOWN) else UNKNOWN,
        "why": why,
        "body": text or "",
    }]
    return out


def _numbered_items(text, heading_contains):
    """A numbered list under a heading, for the remedy steps of a source."""
    lines = (text or "").splitlines()
    start = None
    for index, line in enumerate(lines):
        if line.startswith("#") and heading_contains.lower() in line.lower():
            start = index + 1
            break
    if start is None:
        return []
    items = []
    current = None
    for line in lines[start:start + 120]:
        if re.match(r"^#{1,6}\s", line):
            break
        match = re.match(r"^(\d{1,2})\.\s+(.*)$", line)
        if match:
            if current:
                items.append(current)
            current = {"number": int(match.group(1)),
                       "text": match.group(2).strip()}
            continue
        if current is not None and line.startswith("   ") and line.strip():
            current["text"] += " " + line.strip()
    if current:
        items.append(current)
    out = []
    for item in items:
        text_ = " ".join(item["text"].split())
        lead = re.match(r"^\*\*(.+?)\*\*", text_)
        out.append({"number": item["number"], "text": redact(text_),
                    "lead": redact(lead.group(1).strip(" ."))
                            if lead else redact(text_.split(".")[0])})
    return out


READERS = {
    "runbook": read_runbook,
    "preflight": read_preflight,
    "decisions": read_decisions,
    "exit_criteria": read_exit_criteria,
}


# ================================================================ the assembly


def ops_root():
    """Where the ops estate is, and which kind of nothing when it is not."""
    return exitcriteria.ops_root()


def read_chain(sources, ops, ops_state, now):
    """Every source, opened and parsed. One pass, no fallbacks.

    A source carrying its text inline is how `controls` exercises this exact
    assembly without writing a file. Nothing else sets it.
    """
    chain = []
    for source in sources:
        entry = dict(source)
        entry["attempted_path"] = None
        mtime = None
        if "text" in source:
            state, text = PRESENT, source["text"]
        elif source["where"] == LOC_OPS and ops_state != PRESENT:
            state, text = ops_state, None
        else:
            root = ops if source["where"] == LOC_OPS else REPO_ROOT
            path = os.path.join(root, source["name"].replace("/", os.sep))
            # Kept, and published only when the read FAILED, under
            # `safe_path`. A reader who has to go and look needs the path; a
            # reader who does not should not be shown a home directory.
            entry["attempted_path"] = safe_path(os.path.abspath(path))
            got = exitcriteria.read_source(path)
            state, text, mtime = got["state"], got["text"], got["mtime"]
        parsed = {"rows": [], "why": None}
        if state == PRESENT and text:
            parsed = READERS[source["reader"]](text)
            if not parsed.get("rows"):
                # Read in full and understood as holding nothing this page
                # can turn into a row. The fourth kind of nothing, and the
                # one that reads most like a page with nothing to say.
                state = NO_BLOCK
        entry["state"] = state
        entry["parsed"] = parsed
        entry["parse_why"] = parsed.get("why")
        clock = parsed.get("clock")
        when = clock.get("when") if clock else None
        kind = clock.get("kind") if clock else None
        if when is None and mtime is not None:
            when = datetime.datetime.fromtimestamp(mtime)
            kind = AS_OF_MTIME
        entry["age"] = age_of(when, kind or AS_OF_NONE, now)
        chain.append(entry)
    return chain


def _state_reason(entry):
    """Why a source produced no rows, in the reader's own words."""
    state = entry["state"]
    if state == UNCONFIGURED:
        return ("the ops estate is not configured, so this authority could "
                "not be looked for at all. That is the absence of a place to "
                "look and not the absence of the file")
    if state == ABSENT:
        return ("the authority is not on disk at the path this page tried, "
                "so the question it answers has no answer here")
    if state == UNREADABLE:
        return ("the path exists and could not be read as a file, which is "
                "neither absent nor empty and is nobody's planned state")
    if state == EMPTY:
        return "the file is there and holds nothing"
    if state == NO_BLOCK:
        return (entry.get("parse_why")
                or "it was read in full and nothing in it parsed as a row")
    return None


def assemble(chain, now, poison=None):
    """Every row this page shows, in the order a reader needs them.

    `poison` is the reason every verdict is UNKNOWN regardless of what was
    read - a failed control. It is applied here rather than at the renderer
    so that `describe`, the web page and every test see the same rows.
    """
    by_key = {entry["key"]: entry for entry in chain}
    runbook = by_key.get("runbook")
    decisions = by_key.get("decisions")

    rows = []

    # 1. THE SHORTEST LIST, IN THE RUNBOOK'S OWN ORDER. This is the answer to
    #    "what would change it", and the order is the runbook's judgement
    #    rather than this page's - item 1 first because "nothing else on this
    #    list matters until this one exists".
    p_rows = {}
    shortest = []
    owners = {}
    if runbook and runbook["state"] == PRESENT:
        parsed = runbook["parsed"]
        p_rows = {row["number"]: row for row in parsed["rows"]}
        shortest = parsed["shortest"]
        owners = parsed["owners"]

    void_by_criterion = {}
    if decisions and decisions["state"] == PRESENT:
        for item in decisions["parsed"]["void"]:
            for number in item["criteria"]:
                void_by_criterion.setdefault(number, item)

    claimed_p = set()
    claimed_criteria = set()
    for rank, item in enumerate(shortest, start=1):
        cited = [p_rows[number] for number in item["p_refs"]
                 if number in p_rows]
        claimed_p.update(row["number"] for row in cited)
        claimed_criteria.update(item["criteria"])
        row = _shortest_row(rank, item, cited, runbook, owners,
                            void_by_criterion)
        rows.append(row)

    # 2. PRECONDITIONS THE SHORTEST LIST DOES NOT NAME, and only the ones
    #    that are not MET. A blocker the runbook's own summary omits is
    #    exactly the row a reader of that summary would miss, so it is shown
    #    and labelled as omitted rather than quietly folded in.
    for number in sorted(p_rows):
        if number in claimed_p:
            continue
        row = _precondition_row(p_rows[number], runbook, void_by_criterion)
        rows.append(row)

    # 3. THE OTHER THREE SOURCES' OWN ROWS.
    for key in ("preflight", "exit", "decisions"):
        entry = by_key.get(key)
        if entry is None:
            continue
        if entry["state"] != PRESENT:
            continue
        for item in entry["parsed"]["rows"]:
            if key == "decisions":
                if set(item["criteria"]) & claimed_criteria:
                    # The runbook's shortest list already carries this
                    # question, with this sheet's own withdrawal applied to
                    # it. A second row would be the same question counted
                    # twice, which is how a blocker list grows without
                    # anything getting worse.
                    continue
                rows.append(_decisions_row(item, entry))
            else:
                rows.append(_source_row(item, entry))

    # 4. ONE ROW PER SOURCE THAT COULD NOT BE READ. The question stays on the
    #    screen with UNKNOWN against it. A source that failed and left no row
    #    is the silent-shrink defect: a go/no-go page that answers four
    #    questions today and three tomorrow, with nothing saying which one
    #    went.
    for entry in chain:
        if entry["state"] == PRESENT:
            continue
        rows.append({
            "key": "source:" + entry["key"],
            "question": entry["answers"],
            "verdict": UNKNOWN,
            "reason": _state_reason(entry),
            "owner": OWNER_UNSTATED,
            "homes": [], "where": LOC_UNSTATED,
            "authority": entry["name"],
            "source_key": entry["key"], "source_name": entry["name"],
            "age": entry["age"], "against": None,
            "shortest_rank": None, "omitted_from_shortest": False,
            "dispute": None, "state": entry["state"],
            "attempted_path": entry.get("attempted_path"),
        })

    for index, row in enumerate(rows):
        row.setdefault("state", PRESENT)
        row.setdefault("attempted_path", None)
        row.setdefault("dispute", None)
        row.setdefault("omitted_from_shortest", False)
        row.setdefault("shortest_rank", None)
        row.setdefault("against", None)
        row.setdefault("homes", [])
        row.setdefault("where", LOC_UNSTATED)
        row.setdefault("owner", OWNER_UNSTATED)
        row["order"] = index
        # STALE IS APPLIED AS A VERDICT, NOT AS A FOOTNOTE. A row whose
        # measurement time is older than the threshold, or could not be
        # established at all, no longer carries its verdict: the words it
        # recorded become history and the cell reads STALE. That is a
        # different instruction from NOT MET - re-measure, do not repair -
        # and `VERDICT_TEXT` says so in the glossary the page renders.
        # UNKNOWN AND WITHDRAWN ARE NOT OVERWRITTEN BY STALE, and the
        # direction is the reason. STALE is a weaker statement than either:
        # it says a verdict exists and needs re-reading. An UNKNOWN row has
        # no verdict to re-read, and a WITHDRAWN one had its verdict taken
        # back by the authority - re-measuring restores neither, so rendering
        # them as STALE would hand the reader the wrong instruction.
        if row["age"]["stale"] and row["verdict"] not in (UNKNOWN, WITHDRAWN):
            row["recorded"] = row["verdict"]
            row["recorded_label"] = VERDICT_TEXT[row["verdict"]][0]
            row["verdict"] = STALE
            row["reason"] = (
                "%s, and the reading is %s old against a %s threshold, so "
                "the verdict it recorded (%s) is shown as history. STALE is "
                "not NOT MET: it says re-measure, not repair"
                % (row.get("reason") or "read from the artifact",
                   row["age"]["age_label"], humanise(STALE_SECONDS),
                   row["recorded_label"]))
        elif row["age"]["stale"]:
            row["recorded"] = None
            row["recorded_label"] = None
            row["reason"] = (
                "%s - and the reading is %s old against a %s threshold"
                % (row.get("reason") or "read from the artifact",
                   row["age"]["age_label"], humanise(STALE_SECONDS)))
        else:
            row.setdefault("recorded", None)
            row.setdefault("recorded_label", None)
        if poison:
            row["recorded"] = row["verdict"]
            row["recorded_label"] = VERDICT_TEXT[row["verdict"]][0]
            row["verdict"] = UNKNOWN
            row["reason"] = poison
        row["verdict_label"] = VERDICT_TEXT[row["verdict"]][0]
        row["owner_label"] = OWNER_TEXT[row["owner"]][0]
        row["where_label"] = LOCATION_TEXT[row["where"]][0]
    return rows


def _owner_of(rank, owners):
    return owners.get(rank, OWNER_UNSTATED)


def _shortest_row(rank, item, cited, runbook, owners, void_by_criterion):
    """One item of the shortest list, with the precondition that measured it.

    The item supplies the order and the owner; the cited `P<n>` row supplies
    the verdict and the command. Where an item cites no precondition, its
    verdict comes from its MEMBERSHIP of this list and says so: the runbook
    calls this "the shortest list of things that would change" a NO, so an
    item on it is an outstanding item by the document's own sentence. That is
    a reading of the artifact and not a measurement of the thing.
    """
    clock = runbook["parsed"]["clock"] if runbook else None
    against = runbook["parsed"]["against"] if runbook else {}
    body = " ".join(row.get("body") or "" for row in cited)
    text = item["text"] + " " + body
    homes = homes_in(text)
    if cited:
        verdicts = [row["verdict"] for row in cited]
        if UNKNOWN in verdicts:
            verdict = UNKNOWN
        elif NOT_MET in verdicts:
            verdict = NOT_MET
        else:
            verdict = MET
        reason = ("the runbook's shortest list, item %d, measured by %s. %s"
                  % (item["number"],
                     ", ".join("P%d" % row["number"] for row in cited),
                     "; ".join(
                         filter(None, ("P%d reads %s%s"
                                       % (row["number"],
                                          VERDICT_TEXT[row["verdict"]][0],
                                          (" (%s)" % row["raw"]
                                           if row.get("table_raw")
                                           and row["verdict"] == UNKNOWN
                                           and row["table_raw"]
                                           not in ("UNKNOWN",)
                                           else ""))
                                       for row in cited)))))
        if verdict == MET:
            # AN ITEM ON THE SHORTEST LIST WHOSE PRECONDITION READS MET. The
            # document contradicts itself and this page does not choose: the
            # list says outstanding, the table says done.
            verdict = UNKNOWN
            reason = (
                "the runbook lists this as one of the things that would "
                "change its NO, and the precondition it cites (%s) reads "
                "MET. Those cannot both be current, so UNKNOWN - a list of "
                "outstanding items and a table of verdicts disagreeing "
                "inside one document is not resolved by this page"
                % ", ".join("P%d" % row["number"] for row in cited))
    else:
        verdict = NOT_MET
        reason = ("the runbook's shortest list, item %d. It cites no "
                  "precondition row, so this is the document's own statement "
                  "that the item is outstanding rather than a measurement of "
                  "it" % item["number"])
    row = {
        "key": "shortest:%d" % item["number"],
        "question": item["lead"],
        "detail": item["text"],
        "verdict": verdict,
        "reason": reason,
        "owner": _owner_of(item["number"], owners),
        "homes": homes,
        "where": located(homes),
        "authority": _authority_of(cited),
        "source_key": "runbook",
        "source_name": RUNBOOK,
        "age": None,
        "against": against,
        "shortest_rank": rank,
        "criteria": item["criteria"],
        "p_refs": [r["number"] for r in cited],
    }
    row["age"] = age_of(clock["when"] if clock else None,
                        clock["kind"] if clock else AS_OF_NONE,
                        _NOW_HOLDER["now"])
    _apply_dispute(row, void_by_criterion)
    return row


def _authority_of(cited):
    """The command the runbook says verifies a row, or the harness that ran it.

    Read out of the P section: the document promises "the claim, the command
    that verifies it now, what came back when I ran it". Two of the twelve
    name no command and come back None, which the page renders as a stated
    absence rather than an empty cell.
    """
    for row in cited:
        for line in (row.get("body") or "").splitlines():
            stripped = line.strip()
            if stripped.startswith("$ "):
                return redact(stripped[2:].strip())
    for row in cited:
        match = re.search(r"^\s*harness\s+(\S+)", row.get("body") or "", re.M)
        if match:
            return safe_path(match.group(1))
    return None


def _precondition_row(p_row, runbook, void_by_criterion):
    """A precondition the runbook's own shortest list does not cite."""
    clock = runbook["parsed"]["clock"] if runbook else None
    against = runbook["parsed"]["against"] if runbook else {}
    text = (p_row.get("statement") or "") + " " + (p_row.get("body") or "")
    homes = homes_in(text)
    raw = p_row.get("table_raw") or p_row.get("heading_raw")
    reason = p_row.get("why")
    if not reason:
        if p_row["verdict"] == UNKNOWN and raw and raw.upper() != "UNKNOWN":
            reason = ("the runbook records `%s` for this row, which is not "
                      "one of the three verdicts this page reads, so it is "
                      "UNKNOWN - not MET, and not dropped" % raw)
        else:
            reason = ("precondition P%d of the runbook, read from both its "
                      "table and its own section" % p_row["number"])
    row = {
        "key": "P%d" % p_row["number"],
        "question": p_row.get("statement") or ("precondition P%d"
                                               % p_row["number"]),
        "detail": None,
        "verdict": p_row["verdict"],
        "reason": reason,
        "owner": OWNER_UNSTATED,
        "homes": homes,
        "where": located(homes),
        "authority": _authority_of([p_row]),
        "source_key": "runbook",
        "source_name": RUNBOOK,
        "age": age_of(clock["when"] if clock else None,
                      clock["kind"] if clock else AS_OF_NONE,
                      _NOW_HOLDER["now"]),
        "against": against,
        "shortest_rank": None,
        "omitted_from_shortest": p_row["verdict"] != MET,
        "criteria": criteria_refs(text),
        "p_refs": [p_row["number"]],
        "note": p_row.get("note"),
    }
    _apply_dispute(row, void_by_criterion)
    return row


def _source_row(item, entry):
    """A row a non-runbook source owns outright."""
    homes = homes_in(item.get("body") or "")
    return {
        "key": "%s:%s" % (entry["key"], item["key"]),
        "question": item["question"],
        "detail": None,
        "verdict": item["verdict"],
        "reason": item["why"],
        "owner": OWNER_UNSTATED,
        "homes": homes,
        "where": located(homes),
        "authority": entry["name"],
        "source_key": entry["key"],
        "source_name": entry["name"],
        "age": entry["age"],
        "against": entry["parsed"].get("against") or {},
        "shortest_rank": None,
    }


def _decisions_row(item, entry):
    """One TIER 2 item of the decisions sheet."""
    homes = homes_in(item["title"] + " " + item["body"])
    clock = item.get("clock") or entry["parsed"].get("clock")
    return {
        "key": "decision:%d" % item["number"],
        "question": item["plain"],
        "detail": None,
        "verdict": item["verdict"],
        "reason": item["why"],
        "owner": item["owner"],
        "homes": homes,
        "where": located(homes),
        "authority": "%s, TIER 2 item %d" % (DECISIONS, item["number"]),
        "source_key": entry["key"],
        "source_name": entry["name"],
        "age": age_of(clock["when"] if clock else None,
                      clock["kind"] if clock else AS_OF_NONE,
                      _NOW_HOLDER["now"]),
        "against": entry["parsed"].get("against") or {},
        "shortest_rank": None,
        "criteria": item["criteria"],
    }


def _apply_dispute(row, void_by_criterion):
    """A row another source says has been withdrawn goes UNKNOWN.

    THE LIVE INSTANCE, and the reason this page is worth rendering at all:
    the runbook's shortest list, item 6, asks the operator to name which
    hash-pinned export is the authority for criterion 6. The decisions sheet
    - written five hours later - records that question VOID, closed at
    08:57:16, "there is no sentence for you to say". A page that showed only
    the runbook would have the operator working an item that no longer
    exists.

    It is NOT resolved in the newer document's favour. Two authorities
    disagreeing about one question is UNKNOWN, with both named and both
    dated, which is `src.exitcriteria`'s standing refusal and the operator's
    sentence to settle rather than a page's.
    """
    for number in row.get("criteria") or []:
        item = void_by_criterion.get(number)
        if not item:
            continue
        row["dispute"] = {
            "criterion": number,
            "other_source": DECISIONS,
            "other_item": item["number"],
            "other_title": item["title"],
            "word": item["withdrawn_word"] or "struck through",
        }
        row["recorded"] = row["verdict"]
        row["recorded_label"] = VERDICT_TEXT[row["verdict"]][0]
        row["verdict"] = UNKNOWN
        row["reason"] = (
            "%s - AND `%s` records the same question (criterion %d) as %s in "
            "its item %d. Two authorities disagree about whether this row is "
            "still open, so it is UNKNOWN: naming which of them is the "
            "authority is the operator's sentence, not this page's"
            % (row.get("reason") or "read from the runbook", DECISIONS,
               number, item["withdrawn_word"] or "struck through",
               item["number"]))
        return


#: The render's clock, for the row builders. A module-level holder rather
#: than an argument threaded through six functions - `report` sets it on
#: entry and every row in one render therefore reads one clock. Twelve rows
#: aged against twelve `datetime.now()` calls is twelve measurements
#: presented as one, which is the exact mistake the runbook's own batch clock
#: exists to avoid.
_NOW_HOLDER = {"now": None}


# ==================================================================== verdict


def verdict_of(rows, sources_ok=True, controls_ok=True):
    """GO or NO-GO, and why. The one place this page decides anything.

    ONE GUARD, NOT TWO. The rule in section 4 of TASK 0230 - it must be
    impossible to render GO while any row is UNKNOWN - is enforced here and
    nowhere else, so a test can observe this guard firing rather than
    watching some second check answer first and conclude the rule holds when
    it does not. `tests/test_go_is_impossible_while_a_row_is_unknown.py`
    names it.
    """
    if not controls_ok:
        return NO_GO, ("this page's own controls did not all pass, so its "
                       "reader cannot be shown to work and no verdict it "
                       "produces may be believed")
    if not rows:
        return NO_GO, ("no row was assembled at all. A go/no-go page with "
                       "nothing on it is not a clear board - it is a page "
                       "that read nothing")
    unknown = [row for row in rows if row["verdict"] == UNKNOWN]
    withdrawn = [row for row in rows if row["verdict"] == WITHDRAWN]
    stale = [row for row in rows if row["verdict"] == STALE]
    refused = [row for row in rows if row["verdict"] == NOT_MET]
    if unknown:
        # EVERY OTHER UNRESOLVED BUCKET IS NAMED HERE TOO, not just the one
        # that dominated. A sentence reporting six UNKNOWN on a page that
        # also holds nine STALE and four NOT MET invites the reader to
        # subtract and feel thirteen rows from done, and there is no such
        # position: zero of these nineteen rows reads MET.
        also = []
        if refused:
            also.append("%d NOT MET" % len(refused))
        if stale:
            also.append("%d STALE" % len(stale))
        if withdrawn:
            also.append("%d WITHDRAWN" % len(withdrawn))
        met = len(rows) - len(unknown) - len(refused) - len(stale) \
            - len(withdrawn)
        return NO_GO, (
            "%d of %d rows %s UNKNOWN, so this page cannot say the send is "
            "safe. UNKNOWN is not a near-miss and never becomes a pass: the "
            "row may be true and may be false, and nothing this page can "
            "read says which.%s %d row(s) read MET"
            % (len(unknown), len(rows), "is" if len(unknown) == 1 else "are",
               (" Also on this page: %s." % ", ".join(also)) if also else "",
               met))
    if withdrawn:
        return NO_GO, (
            "%d of %d rows carry a verdict the authority took back. A "
            "withdrawn verdict is not the value it held and is not a pass"
            % (len(withdrawn), len(rows)))
    if stale:
        return NO_GO, (
            "%d of %d rows are STALE - a verdict was recorded and it is "
            "older than %s, or carries no establishable measurement time at "
            "all. That is a different instruction from NOT MET: re-measure "
            "these, do not repair them"
            % (len(stale), len(rows), humanise(STALE_SECONDS)))
    if refused:
        return NO_GO, (
            "every row is established and %d of %d %s NOT MET. The canary "
            "does not go"
            % (len(refused), len(rows), "is" if len(refused) == 1 else "are"))
    if not sources_ok:
        return NO_GO, (
            "every row this page assembled reads MET - and this page has "
            "just reported that it could not read or parse every source it "
            "is configured with. A clearance asserted over a set it admits "
            "it may not have read in full is exactly the claim it has no "
            "standing to make")
    return GO, (
        "all %d rows read MET, every source was read and parsed, every row "
        "carries a measurement time inside %s, and all controls passed. That "
        "is a reading of other people's measurements and is only as good as "
        "the dates beside them" % (len(rows), humanise(STALE_SECONDS)))


def shortest_list_of(rows):
    """What would change a NO, in order, and nothing that would not.

    The runbook's own order first, because the order is its judgement:
    "nothing else on this list matters until this one exists". Then the
    blockers it does not name, then the sources that could not be read.
    """
    out = []
    ranked = sorted((row for row in rows
                     if row["shortest_rank"] and row["verdict"] != MET),
                    key=lambda row: row["shortest_rank"])
    others = [row for row in rows
              if not row["shortest_rank"] and row["verdict"] != MET]
    for position, row in enumerate(ranked + others, start=1):
        out.append({
            "position": position,
            "what": row["question"],
            "verdict": row["verdict"],
            "verdict_label": row["verdict_label"],
            "owner": row["owner"],
            "owner_label": row["owner_label"],
            "source_name": row["source_name"],
            "from_runbook_list": bool(row["shortest_rank"]),
            "runbook_rank": row["shortest_rank"],
            "key": row["key"],
        })
    return out


# =================================================================== controls
#
# THREE CHECKS, EVERY RENDER, PRINTING PASS OR FAIL. They run the real
# assembly - `read_chain`, then `assemble`, then `verdict_of` - against
# fixture text, so a control passing is evidence about the path the page uses
# and not about a parallel one written to be green.
#
# The third is the one that matters. A page hard-wired to NO-GO would satisfy
# every refusal in this module and be worthless, and this lane has already
# shipped a check that could not fire. So one fixture clears every blocker
# and the page is required to say GO.

#: A path that must not exist, for the absence control. Asserted absent by
#: the control itself: if somebody creates it the control FAILS rather than
#: quietly measuring nothing.
ABSENT_FIXTURE = "docs/fixtures/gonogo-control-file-that-must-not-exist.md"

#: Present, readable, and holding nothing this page can parse - in its most
#: dangerous shape, which LOOKS like a runbook. It has the title, it has a
#: section 2, and it has neither a `P<n>` table nor a shortest list, so a
#: reader with a weaker threshold would render it as a clear board.
UNPARSEABLE_RUNBOOK = """# CANARY-01 - GO / NO-GO RUNBOOK

The preconditions have not been re-measured since the last dispatch and the
table below is not written yet.

## 2. PRECONDITIONS

    the brake            fine
    the write door       fine
"""


def _fixture_clock(now):
    """A fixture's measurement time, derived from the render's clock.

    NOT a hardcoded date, and the reason is this module's own staleness rule.
    A fixture stamped `2026-10-16` would read eleven hours old by lunchtime
    and the GO control would fail - for a reason that has nothing to do with
    whether the page can render GO, which is the one thing that control
    exists to prove. So the fixture says it was measured one minute ago, and
    the staleness rule is proven separately, by a test that ages a row on
    purpose.
    """
    when = (now - datetime.timedelta(minutes=1)).replace(microsecond=0)
    return when.strftime("%Y-%m-%d %H:%M:%S")


def all_clear_fixtures(now):
    """Four documents in which every blocker is cleared.

    Written in the artifacts' own shapes - the same headline, the same batch
    clock, the same `P<n>` table, the same four preflight counts, the same
    `TIER 2` heading - because a fixture in a shape the real parser does not
    meet proves nothing about the real parser.
    """
    clock = _fixture_clock(now)
    day = clock.split(" ")[0]
    runbook = """# CANARY-01 - GO / NO-GO RUNBOOK

# YES. CANARY-01 CAN SEND TODAY, %(day)s.

The shortest list of things that would change that is empty: every
precondition below reads MET and no decision is open.

    batch clock   local %(clock)s +0200
    origin/master  0000000000000000000000000000000000000000  verified

## 2. PRECONDITIONS

    P1   the brake is in the sending tree                        MET
    P2   the write door covers every send path                   MET

### P1 - the brake is in the sending tree. **MET.**

    $ git cat-file -e origin/master:src/haltfile.py
    present

### P2 - the write door covers every send path. **MET.**

    $ py -3 scripts/write_path_denominator.py
    BYPASS the door        : 0
""" % {"clock": clock, "day": day}

    preflight = """# CANARY-01 preflight - %(day)s

**CANARY-01 IS CLEARED TO SEND.**

    contacts assessed             10
    cleared                       10
    excluded                       0
    NOT CLEARED because UNKNOWN    0

Measured %(clock)s in `wt-fixture`, at SHA `0000000000`.
""" % {"clock": clock, "day": day}

    # Nine MET rows in the shape `src.exitcriteria`'s own parser reads, so
    # the conjunction it computes is MET rather than short of nine.
    nine = "\n".join("    %d  a fixture criterion     MET" % number
                     for number in range(1, 10))
    exit_text = """# CANARY-01 - EXIT CRITERIA, FIXTURE - %(day)s

Measured %(clock)s.

## 0. THE TABLE

%(nine)s
""" % {"clock": clock, "day": day, "nine": nine}

    decisions = """# DECISIONS OPEN - %(clock)s local (fixture)

## TIER 2 - the canary's own four blockers

Nothing is open. None of these can be closed by a lane.

## TIER 3 - sentences only the operator can say

### 7. A decision that is not the canary's
""" % {"clock": clock}

    return {"runbook": runbook, "preflight": preflight,
            "exit": exit_text, "decisions": decisions}


def _inline(sources, texts):
    """The configured sources, each carrying fixture text instead of a path."""
    out = []
    for source in sources:
        entry = dict(source)
        if source["key"] in texts:
            entry["text"] = texts[source["key"]]
        out.append(entry)
    return tuple(out)


def _run(sources, now):
    """The real assembly, over whatever sources it is given."""
    ops, ops_state = ops_root()
    chain = read_chain(sources, ops, ops_state, now)
    previous = _NOW_HOLDER["now"]
    _NOW_HOLDER["now"] = now
    try:
        rows = assemble(chain, now)
    finally:
        _NOW_HOLDER["now"] = previous
    sources_ok = all(entry["state"] == PRESENT for entry in chain)
    verdict, why = verdict_of(rows, sources_ok=sources_ok, controls_ok=True)
    return chain, rows, verdict, why


def controls(now=None):
    """Three checks, run on every render, each printing PASS or FAIL."""
    now = now or datetime.datetime.now()
    checks = []

    # 1. A SOURCE THAT IS NOT THERE. Its question must stay on the screen,
    #    carrying UNKNOWN, and the verdict must be NO-GO.
    absent = os.path.join(REPO_ROOT, ABSENT_FIXTURE.replace("/", os.sep))
    if os.path.exists(absent):
        checks.append({
            "name": "absent source renders UNKNOWN",
            "ok": False,
            "detail": ("the control's own fixture path exists, so this check "
                       "would measure a readable file rather than an absent "
                       "one. Delete %s" % safe_path(ABSENT_FIXTURE)),
        })
    else:
        sources = tuple(
            dict(source, where=LOC_REPO, name=ABSENT_FIXTURE)
            if source["key"] == "runbook" else source
            for source in SOURCES)
        chain, rows, verdict, _ = _run(sources, now)
        entry = [item for item in chain if item["key"] == "runbook"][0]
        row = [item for item in rows if item["key"] == "source:runbook"]
        ok = (entry["state"] == ABSENT and len(row) == 1
              and row[0]["verdict"] == UNKNOWN and verdict == NO_GO)
        checks.append({
            "name": "absent source renders UNKNOWN",
            "ok": ok,
            "detail": ("the runbook pointed at a path that does not exist: "
                       "state %s, its question rendered as %d row(s) reading "
                       "%s, page verdict %s"
                       % (entry["state"], len(row),
                          row[0]["verdict_label"] if row else "no row",
                          VERDICT_LABEL[verdict])),
        })

    # 2. A SOURCE THAT IS THERE AND DOES NOT PARSE. Same outcome, and the
    #    reason has to be shown rather than swallowed.
    sources = _inline(SOURCES, {"runbook": UNPARSEABLE_RUNBOOK})
    chain, rows, verdict, _ = _run(sources, now)
    entry = [item for item in chain if item["key"] == "runbook"][0]
    row = [item for item in rows if item["key"] == "source:runbook"]
    ok = (entry["state"] == NO_BLOCK and len(row) == 1
          and row[0]["verdict"] == UNKNOWN and bool(row[0]["reason"])
          and verdict == NO_GO)
    checks.append({
        "name": "unparseable source renders UNKNOWN with a reason",
        "ok": ok,
        "detail": ("a runbook-shaped document with no precondition table and "
                   "no shortest list: state %s, %d row(s) reading %s, reason "
                   "%s, page verdict %s"
                   % (entry["state"], len(row),
                      row[0]["verdict_label"] if row else "no row",
                      "shown" if row and row[0]["reason"] else "MISSING",
                      VERDICT_LABEL[verdict])),
    })

    # 3. EVERY BLOCKER CLEARED MUST RENDER GO. Without this the page could be
    #    hard-wired to NO-GO and nobody would know - and NO-GO is the answer
    #    it gives every real day, so no amount of looking at it would tell.
    sources = _inline(SOURCES, all_clear_fixtures(now))
    chain, rows, verdict, why = _run(sources, now)
    not_met = [row["key"] for row in rows if row["verdict"] != MET]
    ok = verdict == GO and not not_met and bool(rows)
    checks.append({
        "name": "a fully cleared fixture renders GO",
        "ok": ok,
        "detail": ("four fixture documents in the artifacts' own shapes with "
                   "every blocker cleared: %d row(s), %d not MET%s, page "
                   "verdict %s"
                   % (len(rows), len(not_met),
                      (" (%s)" % ", ".join(not_met[:4])) if not_met else "",
                      VERDICT_LABEL[verdict])),
    })
    return checks


# ===================================================================== report


def report(now=None, sources=None):
    """The page. Read-only and side-effect-free.

    No file is written, no provider is reached, no socket is opened, no
    credential is read and no git command is run.
    """
    now = (now or datetime.datetime.now()).replace(microsecond=0)
    ops, ops_state = ops_root()

    # The controls run FIRST, and `controls` is looked up on the module at
    # call time so a test can break one and watch the poisoning happen.
    checks = globals()["controls"](now=now)
    failed = [check["name"] for check in checks if not check["ok"]]
    poison = None
    if failed:
        poison = ("this page's own control(s) %s FAILED, so its reader cannot "
                  "be shown to work and NO verdict it produces may be "
                  "believed. Every row is UNKNOWN until that is fixed"
                  % ", ".join(failed))

    chain = read_chain(sources or SOURCES, ops, ops_state, now)
    previous = _NOW_HOLDER["now"]
    _NOW_HOLDER["now"] = now
    try:
        rows = assemble(chain, now, poison=poison)
    finally:
        _NOW_HOLDER["now"] = previous

    sources_ok = all(entry["state"] == PRESENT for entry in chain)
    verdict, why = verdict_of(rows, sources_ok=sources_ok,
                              controls_ok=not failed)

    tally = {MET: 0, NOT_MET: 0, UNKNOWN: 0, WITHDRAWN: 0, STALE: 0}
    for row in rows:
        tally[row["verdict"]] += 1

    runbook = [entry for entry in chain if entry["key"] == "runbook"]
    headline = None
    headline_verdict = None
    if runbook and runbook[0]["state"] == PRESENT:
        headline = runbook[0]["parsed"].get("headline")
        headline_verdict = runbook[0]["parsed"].get("headline_verdict")

    data = {
        "rendered_at": now.isoformat(" "),
        "verdict": verdict,
        "verdict_label": VERDICT_LABEL[verdict],
        "verdict_why": why,
        "shortest": shortest_list_of(rows),
        "rows": rows,
        "blockers": [row for row in rows if row["verdict"] != MET],
        "cleared": [row for row in rows if row["verdict"] == MET],
        "tally": tally,
        "controls": checks,
        "controls_ok": not failed,
        "controls_failed": failed,
        "sources_ok": sources_ok,
        "ops_state": ops_state,
        # The directory's NAME, never its path. A screen printing an absolute
        # path is a screen naming somebody's home directory in a screenshot.
        "ops_name": os.path.basename(ops.rstrip("\\/")) if ops else None,
        "variable": OPS_DIR,
        "stale_seconds": STALE_SECONDS,
        "stale_label": humanise(STALE_SECONDS),
        "sources": [{
            "key": entry["key"], "name": entry["name"],
            "state": entry["state"], "answers": entry["answers"],
            "age": entry["age"],
            "rows": len(entry["parsed"].get("rows") or []),
            "why": entry.get("parse_why"),
            "reason": _state_reason(entry),
            "attempted_path": (entry.get("attempted_path")
                               if entry["state"] != PRESENT else None),
            "against": against_label(entry["parsed"].get("against") or {}),
        } for entry in chain],
        "unread": [entry["name"] for entry in chain
                   if entry["state"] != PRESENT],
        "disputes": [row["key"] for row in rows if row.get("dispute")],
        "omitted": [row["key"] for row in rows
                    if row.get("omitted_from_shortest")],
        "verdict_glossary": [{"label": label, "why": why_}
                             for label, why_ in VERDICT_TEXT.values()],
        "owner_glossary": [{"label": label, "why": why_}
                           for label, why_ in OWNER_TEXT.values()],
        "location_glossary": [{"label": label, "why": why_}
                              for label, why_ in LOCATION_TEXT.values()],
        # WHAT THE RUNBOOK'S OWN FIRST LINE SAYS, kept beside the computed
        # verdict rather than used as it. Two statements of one answer: if
        # they disagree the page says so instead of picking.
        #
        # NAMED `runbook_headline` AND NOT `headline`, and the reason is a
        # defect this collision actually caused: the service layer adds its
        # own one-line `headline` for the top of the page, and while both
        # used the same key the page's notice about "the runbook's own first
        # line" printed the service layer's sentence instead of the
        # document's.
        "runbook_headline": headline,
        "runbook_headline_verdict": headline_verdict,
        "runbook_headline_label": (VERDICT_LABEL[headline_verdict]
                                   if headline_verdict else None),
        "runbook_headline_agrees": (None if headline_verdict is None
                                    else headline_verdict == verdict),
    }
    data["owners"] = {
        OWNER_CONSTRUCTION: len([row for row in data["blockers"]
                                 if row["owner"] == OWNER_CONSTRUCTION]),
        OWNER_OPERATOR: len([row for row in data["blockers"]
                             if row["owner"] == OWNER_OPERATOR]),
        OWNER_UNSTATED: len([row for row in data["blockers"]
                             if row["owner"] == OWNER_UNSTATED]),
    }
    return data


REFUSALS = (
    ("measure anything",
     "not one verdict on this page is produced here. Every one is read out "
     "of a document another lane wrote, named, and shown with its age - "
     "because a second instrument measuring the same thing is a second "
     "authority, and two authorities for one number is this repository's own "
     "named defect. There is no git call, no provider call and no socket"),
    ("print a number no artifact contains",
     "every figure here is quoted from a source and attributed to it. The "
     "only numbers this page computes are counts of its own rows, and the "
     "rows are all on screen to be counted"),
    ("call a verdict current because it is written down",
     "a reading older than %s renders STALE, with the verdict it recorded "
     "shown as history. The runbook was rewritten at 03:58 because four of "
     "its own verdicts had changed in fifty-six minutes; age is the field "
     "that makes that visible instead of invisible" % humanise(STALE_SECONDS)),
    ("resolve a disagreement between two authorities",
     "where two sources answer one question differently - and that is live, "
     "the runbook's item 6 against the decisions sheet's item 8 - the row "
     "renders UNKNOWN with both named and both dated. Not resolved by "
     "recency, not by rank. Naming the authority is the operator's sentence"),
    ("let a row disappear",
     "a source that is absent, unreadable, empty or unparseable still "
     "produces its row, carrying UNKNOWN and the reason. A question that "
     "silently leaves a go/no-go screen is indistinguishable from a question "
     "that was answered yes"),
    ("render GO while any row is UNKNOWN",
     "enforced in one place, `verdict_of`, and pinned by a test named after "
     "the rule. UNKNOWN is not a softer NOT MET: the row may be true and may "
     "be false, and nothing this page can read says which"),
    ("believe itself when its controls fail",
     "three controls run on every render. If any fails, every row on the "
     "page is UNKNOWN and the verdict is NO-GO - including the control that "
     "proves a fully cleared fixture renders GO, without which this page "
     "could be hard-wired to the answer it gives every real day"),
)


def describe(data=None):
    """The same reading, for a terminal. Same rows, same refusals."""
    data = data if data is not None else report()
    out = ["CANARY-01 - can this send right now?  read at %s"
           % data["rendered_at"], ""]
    out.append("  %s" % data["verdict_label"])
    out.append("    " + data["verdict_why"])
    out.append("")
    for check in data["controls"]:
        out.append("  %-4s %-44s %s" % ("PASS" if check["ok"] else "FAIL",
                                        check["name"], check["detail"]))
    out.append("")
    if not data["controls_ok"]:
        out.append("  THE READER IS NOT TRUSTWORTHY: every row below is "
                   "UNKNOWN because a control failed.")
        out.append("")
    out.append("  the sources this read used, and how old each one is:")
    for source in data["sources"]:
        out.append("    %-40s %-9s %-10s %s"
                   % (source["name"][:40], source["state"],
                      source["age"]["age_label"],
                      source["against"] or "names no SHA"))
        if source["reason"]:
            out.append("        " + source["reason"][:140])
    out.append("")
    if data["shortest"]:
        out.append("  THE SHORTEST LIST, in the runbook's own order:")
        for item in data["shortest"]:
            out.append("    %2d  %-9s %-13s %s"
                       % (item["position"], item["verdict_label"],
                          item["owner_label"], item["what"][:90]))
    else:
        out.append("  nothing is outstanding on any source this page read.")
    out.append("")
    out.append("  every row:")
    for row in data["rows"]:
        out.append("    %-9s %-13s %-10s %s"
                   % (row["verdict_label"], row["owner_label"],
                      row["age"]["age_label"], row["question"][:80]))
        if row["reason"]:
            out.append("        " + row["reason"][:150])
    out.append("")
    out.append("  %s - over the %d sources named above and no others"
               % (", ".join("%d %s" % (data["tally"][verdict],
                                       VERDICT_TEXT[verdict][0])
                            for verdict in (MET, NOT_MET, UNKNOWN,
                                            WITHDRAWN, STALE)),
                  len(data["sources"])))
    if data["runbook_headline"] is not None:
        out.append("  the runbook's own first line says %s and this page "
                   "says %s: %s"
                   % (data["runbook_headline_label"], data["verdict_label"],
                      "they agree" if data["runbook_headline_agrees"]
                      else "THEY DISAGREE"))
    return "\n".join(out)


if __name__ == "__main__":                                  # pragma: no cover
    import sys

    data = report()
    print(describe(data))
    # 0 only on GO. A screen is read; an exit code is checked by something
    # else, and "the canary cannot send" is not a success.
    sys.exit(0 if data["verdict"] == GO else 2)
