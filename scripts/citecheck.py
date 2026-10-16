#!/usr/bin/env python3
"""Every `path:line` citation in a markdown file, checked against HEAD.

READ ONLY, and it writes nothing at all.

    py -3 scripts/citecheck.py docs/SOME-REPORT.md [more.md ...]
    py -3 scripts/citecheck.py --self-test
    py -3 scripts/citecheck.py --json docs/SOME-REPORT.md

## WHY THIS EXISTS

Three times in one night, in one lane, a `file:line` citation was written from
memory and was wrong. `src/preflight.provenance()` verifies the SHA a report
was measured at; **nothing verified a line number**, and the line number is
what a reader opens the file to. `docs/NINE-HUNDRED-SENDS-ONE-CONFIRMED-
TOUCH-2026-10-16.md` carried `scripts/bison_watch_loop.py:643` where the
symbol is two lines up, and `src/leadobserve.py:789` where it is one line
down - on the four citations carrying that document's single load-bearing
claim.

A document whose citations are unchecked is a document whose claims are
unchecked.

## SIX STATES, AND FIVE OF THEM ARE NOT `OK`

    OK             the cited symbol is on the cited line (or inside the range)
    MOVED          the symbol is in the file, on a DIFFERENT line, which is
                   named. The state that would have caught the two above in
                   nine seconds
    BROKEN         no such file at HEAD, or the line is past end-of-file
    UNVERIFIABLE   the citation carries no symbol, so there is nothing to
                   check. **NOT counted as checked** - a bare `file:123` is a
                   claim nobody can test, and printing it as OK is how an
                   instrument that checks nothing reports clean
    REFUSED        the citation points into a path this run may not open.
                   A sixth state the brief did not ask for, and it is
                   necessary: `src/providers/*` and the watch loops are
                   outside the suppression lane's boundary, so "I may not
                   look" has to be visibly different from "I looked and it is
                   fine". See LANE_FORBIDDEN
    ERROR          the check itself failed - git unavailable, undecodable
                   bytes. Never silent, never OK

`UNVERIFIABLE` is printed with its own total and **a document may not be
called verified while that count is above zero.** The summary says the number
out loud.

## THE LINE-ENDING TRAP, ASSERTED RATHER THAN ASSUMED

Five lane worktrees are CRLF and the main checkout is LF (measured
2026-10-15, recorded in the standing rules). A line NUMBER cannot depend on
that - a terminator is not a line - but "cannot" is an argument, so this
checks it: every citation is resolved against the **blob at HEAD**, which is
LF, and the working tree's own line count is compared against it. A
disagreement is reported per file, with the ending each one used, and it
makes the file's citations ERROR rather than OK.

## WHAT IT DOES NOT DO

No network call. No provider call. It writes nothing - not even a cache - and
`--json` goes to stdout like everything else here. It reads `git show`, the
markdown files named on the command line, and the files they cite.
"""
import argparse
import json
import os
import re
import subprocess

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

OK = "OK"
MOVED = "MOVED"
BROKEN = "BROKEN"
UNVERIFIABLE = "UNVERIFIABLE"
REFUSED = "REFUSED"
ERROR = "ERROR"

#: Every state, in the order a summary prints them. `OK` first because it is
#: the only one that is good news, and the rest because each is a different
#: reason a reader must not trust the citation.
STATES = (OK, MOVED, BROKEN, UNVERIFIABLE, REFUSED, ERROR)

#: States that make the run fail. `UNVERIFIABLE` does NOT - it is a citation
#: nobody can check rather than a citation that is wrong - but it is counted
#: and said out loud, and a document with any is not verified.
FAILING = (MOVED, BROKEN, REFUSED, ERROR)

#: PATHS THIS RUN MAY NOT OPEN, with the reason, because a refusal with no
#: reason is indistinguishable from a bug. These are the suppression lane's
#: standing boundary: `src/providers/*`, the watch loops and the credential
#: file. A citation into one of them is REFUSED - never OK, never
#: UNVERIFIABLE, both of which would read as "nothing to worry about".
LANE_FORBIDDEN = (
    ("src/providers/", "the lane's boundary forbids reading src/providers/*"),
    ("scripts/bison_watch_loop.py", "a monitor loop, outside the boundary"),
    ("scripts/heyreach_watch_loop.py", "a monitor loop, outside the boundary"),
    ("config/.env", "a credential file, never read and never printed"),
    ("work/", "production state, outside the boundary"),
)

#: The citation forms this extractor recognises. Deliberately narrow: a
#: pattern that matched `3:14` in prose would make every document full of
#: findings nobody wrote.
#:
#: `src/x.py:144`, `src/x.py:400-404`, `src/x.py:144,178,220` and the bare
#: `report.py:97` all occur in this estate's own documents, so all four are
#: matched. The continuation list is kept: `:144,178,220` is three claims and
#: reporting it as one would hide two of them.
CITATION = re.compile(
    r"(?P<path>[A-Za-z0-9_][A-Za-z0-9_./-]*"
    r"\.(?:py|md|txt|json|jsonl|cfg|toml|ini|yml|yaml|sh|service|timer))"
    r":(?P<first>\d+)(?P<rest>(?:[-,]\d+)*)")

#: A symbol is looked for in this much of the text after the citation. Long
#: enough for a quoted line of code, short enough that the next sentence's
#: identifiers do not become this citation's evidence.
LOOKAHEAD = 160

#: Words that are not evidence of anything. A citation followed only by
#: `CONFIRMED` carries no symbol, and treating `CONFIRMED` as the symbol to
#: look for would report BROKEN for every correct citation in the estate.
NOT_A_SYMBOL = {
    "confirmed", "correct", "wrong", "and", "the", "see", "measured", "with",
    "from", "not", "but", "its", "which", "this", "that", "where", "exactly",
    "unknown", "pass", "fail", "yes", "no", "ours", "default", "by", "at",
    "in", "is", "are", "was", "were", "it", "a", "an", "of", "on", "to",
    "line", "lines", "file", "files", "page", "pages", "rows", "row", "say",
    "says", "said", "every", "none", "all", "both", "one", "two", "three",
    "four", "still", "already", "again", "only", "also", "same", "other",
}


#: WHICH GUARD ANSWERED, per verdict. Three different facts come out as
#: BROKEN - no file, a line past end-of-file, and a symbol that is nowhere in
#: the file - and a control that observed only `BROKEN` could not tell them
#: apart. Measured: the "a missing file is read as empty" blinding below
#: reddened NOTHING until these existed, because the fixture's verdict was
#: still BROKEN for a different reason. A control must observe the guard it
#: tests, not the verdict it produces.
BECAUSE_NO_FILE = "no_file_at_head"
BECAUSE_PAST_EOF = "past_end_of_file"
BECAUSE_SYMBOL_ABSENT = "symbol_absent_from_file"
BECAUSE_SYMBOL_ELSEWHERE = "symbol_on_another_line"
BECAUSE_SYMBOL_ON_LINE = "symbol_on_the_cited_line"
BECAUSE_NO_SYMBOL = "the_citation_names_no_symbol"
BECAUSE_BOUNDARY = "outside_this_runs_boundary"
BECAUSE_CHECK_FAILED = "the_check_itself_failed"


class Refused(Exception):
    """This path may not be opened by this run. Not an error; a boundary."""


def _git(args):
    done = subprocess.run(["git"] + list(args), cwd=ROOT,
                          capture_output=True, timeout=60)
    return done.returncode, done.stdout, (done.stderr or b"").decode(
        "utf-8", "replace")


_HEAD_TREE = {}


def head_files():
    """Every path at HEAD, by basename. Read once per run, never written.

    Only used to TELL A READER what a bare `report.py:97` would have
    resolved to. It does not change the verdict: the citation as written does
    not resolve from the repository root, and a citation a reader cannot
    paste is broken whatever it was meant to say.
    """
    if _HEAD_TREE:
        return _HEAD_TREE
    rc, out, err = _git(["ls-tree", "-r", "--name-only", "HEAD"])
    if rc != 0:
        raise RuntimeError("git could not list HEAD: %s" % err.strip()[:160])
    for path in out.decode("utf-8", "replace").splitlines():
        _HEAD_TREE.setdefault(os.path.basename(path), []).append(path)
    return _HEAD_TREE


def head_sha():
    rc, out, err = _git(["rev-parse", "HEAD"])
    if rc != 0:
        raise RuntimeError("git could not name HEAD: %s" % err.strip()[:160])
    return out.decode("ascii", "replace").strip()


def forbidden(path):
    """(True, why) if this citation's path is outside the boundary."""
    normal = path.replace("\\", "/").lstrip("./")
    for prefix, why in LANE_FORBIDDEN:
        if normal == prefix or normal.startswith(prefix):
            return True, why
    return False, None


def read_at_head(path):
    """(lines, note) for `path` at HEAD, with the working tree cross-checked.

    THE BLOB IS THE AUTHORITY, for the reason in the module docstring: it is
    LF in every tree, so a citation means the same thing from the CRLF lane
    worktrees and from the LF main checkout. The working tree is read only to
    CHECK that claim, never to answer the citation.
    """
    bad, why = forbidden(path)
    if bad:
        raise Refused(why)
    sha = head_sha()
    rc, blob, err = _git(["show", "%s:%s" % (sha, path)])
    if rc != 0:
        raise FileNotFoundError(
            "no %s at HEAD (%s): %s" % (path, sha[:9], err.strip()[:120]))
    try:
        text = blob.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RuntimeError("%s at HEAD is not utf-8: %s" % (path, exc))
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    note = "%d lines in the HEAD blob" % len(lines)

    disk = os.path.join(ROOT, path.replace("/", os.sep))
    if os.path.exists(disk):
        with open(disk, "rb") as handle:
            raw = handle.read()
        ending = ("CRLF" if b"\r\n" in raw
                  else "LF" if b"\n" in raw else "none")
        if b"\r\n" in raw and raw.count(b"\n") != raw.count(b"\r\n"):
            ending = "MIXED"
        on_disk = raw.replace(b"\r\n", b"\n").split(b"\n")
        if on_disk and on_disk[-1] == b"":
            on_disk.pop()
        # ASSERTED, NOT ASSUMED. A terminator is not a line, so these two
        # counts must agree whatever the tree's endings are.
        if len(on_disk) != len(lines):
            raise RuntimeError(
                "%s: the HEAD blob has %d lines and the working tree has %d "
                "(%s). Line numbers are not comparable, so no citation into "
                "this file can be answered"
                % (path, len(lines), len(on_disk), ending))
        note += ", working tree agrees (%s)" % ending
    else:
        note += ", not in the working tree"
    return lines, note


#: An identifier worth looking for. Three characters minimum, and it has to
#: start like a name - which is what rules out the backticked `,` that the
#: first version of this extractor accepted as a symbol and then found on
#: half the lines of every file it opened.
IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]{2,}")


def symbol_near(text, after):
    """The identifier a citation is claiming, or None. Two forms only.

    TWO, AND PROSE IS NOT ONE OF THEM. The estate's documents cite in
    exactly these shapes:

        `src/suppression.py:114` `UNKNOWN_IS_NOT_A_PASS = True`   backticked
            scripts/bison_watch_loop.py:643   on_queue = _bounce(...)  code
        | `src/leadobserve.py:400-404` |              nothing: UNVERIFIABLE
        see `docs/X.md:288`, as stated above          nothing: UNVERIFIABLE
        `src/x.py:757-767`, in `f`' own docstring     nothing: UNVERIFIABLE

    The last two are why a bare following WORD is not accepted and why a
    backticked one must be ADJACENT. Measured: `stated`, `across` and `, in`
    were taken as symbols and reported MOVED, charging a document with
    claiming a preposition is on a line; and `record_bounces`, named in
    prose after a correct range citation, was reported MOVED against the
    docstring the range actually quotes. An UNVERIFIABLE is a citation
    nobody can check, which is true of all of those; a MOVED is a false
    accusation, and this tool exists to stop those.

    In an indented code block there are no backticks to use, and that form
    carries the citations this whole tool exists for - so inside one, the
    rest of the line IS the claim.
    """
    window = text[after:after + LOOKAHEAD].split("\n")[0]
    line_start = text.rfind("\n", 0, after) + 1
    in_code_block = text[line_start:line_start + 4] == "    "

    # DROP THE CITATION'S OWN CLOSING BACKTICK FIRST. Without this, the
    # span-finder below pairs it with the opening backtick of the symbol and
    # returns the whitespace between them - so the symbol is never reached
    # and a perfectly correct citation reads UNVERIFIABLE.
    window = window.lstrip()
    if window.startswith("`"):
        window = window[1:].lstrip()

    # ADJACENT OR NOT AT ALL. See this function's docstring: a backticked
    # name with prose in front of it is context, not the citation's claim.
    adjacent = re.match(r"`([^`]+)`", window)
    for candidate in ([adjacent.group(1)] if adjacent else []):
        token = candidate.strip()
        # A CITATION IS NOT EVIDENCE FOR ANOTHER CITATION, and a PATH is not
        # a symbol on a line. Both were being accepted, and both produce a
        # MOVED out of nothing: the first identifier of
        # `docs/SOMETHING.md:288` is `docs`, which is on five lines of any
        # markdown file.
        if CITATION.match(token) or "/" in token:
            continue
        found = IDENTIFIER.search(token)
        if found and found.group(0).lower() not in NOT_A_SYMBOL:
            return token, "backticked"
    if in_code_block:
        for candidate in IDENTIFIER.findall(window):
            if candidate.lower() in NOT_A_SYMBOL:
                continue
            return candidate, "code block"
    return None, ("no backticked symbol immediately after the citation"
                  if not in_code_block else
                  "nothing identifier-shaped after the citation")


def _on_line(symbol, line):
    """Is this symbol present on this line?

    The FIRST IDENTIFIER of the quoted fragment, because a document quoting
    `confirm_email_touches(..., live=live,` has elided the middle of the call
    and an exact match would fail on a citation that is perfectly correct.
    The rest of the fragment is prose as far as this comparison goes.
    """
    found = IDENTIFIER.search(symbol or "")
    needle = found.group(0) if found else (symbol or "").strip()
    return bool(needle) and needle in line


def _lines_holding(symbol, lines):
    return [n for n, line in enumerate(lines, 1) if _on_line(symbol, line)]


def citations_in(text):
    """Every citation in a markdown text, in order, one per claimed line."""
    out = []
    for match in CITATION.finditer(text):
        path = match.group("path")
        numbers = [int(match.group("first"))]
        for extra in re.finditer(r"[-,](\d+)", match.group("rest") or ""):
            numbers.append(int(extra.group(1)))
        separators = set(re.findall(r"[-,]", match.group("rest") or ""))
        symbol, how = symbol_near(text, match.end())
        before = text.count("\n", 0, match.start()) + 1
        if "-" in separators and len(numbers) == 2:
            spans = [(numbers[0], numbers[1])]
        else:
            spans = [(n, n) for n in numbers]
        for start, end in spans:
            out.append({"path": path, "start": start, "end": end,
                        "symbol": symbol, "symbol_from": how,
                        "cited_in_line": before,
                        "text": match.group(0)})
    return out


def check_one(citation, sources=None):
    """One citation's verdict. `sources` replaces the reader, for the controls.

    `sources` is `path -> (lines, note)` and may raise `Refused`,
    `FileNotFoundError` or anything else - the three map to REFUSED, BROKEN
    and ERROR respectively, and none of them maps to OK.
    """
    read = sources or read_at_head
    row = dict(citation)
    try:
        lines, note = read(citation["path"])
    except Refused as exc:
        row.update({"state": REFUSED, "because": BECAUSE_BOUNDARY,
                    "why": str(exc), "note": None})
        return row
    except FileNotFoundError as exc:
        why = str(exc)
        try:
            same_name = head_files().get(os.path.basename(citation["path"]))
        except Exception:                                       # noqa: BLE001
            same_name = None
        if same_name and len(same_name) == 1:
            row["resolves_to"] = same_name[0]
            why += (". The repository holds exactly one %s, at %s - the "
                    "citation is missing its directory"
                    % (os.path.basename(citation["path"]), same_name[0]))
        elif same_name:
            row["resolves_to"] = same_name
            why += (". The repository holds %d files with that name (%s), so "
                    "the citation is ambiguous as well as unresolvable"
                    % (len(same_name), ", ".join(same_name[:4])))
        row.update({"state": BROKEN, "because": BECAUSE_NO_FILE,
                    "why": why, "note": None})
        return row
    except Exception as exc:                                    # noqa: BLE001
        row.update({"state": ERROR, "because": BECAUSE_CHECK_FAILED,
                    "why": "%s: %s" % (type(exc).__name__, str(exc)[:200]),
                    "note": None})
        return row
    row["note"] = note
    if citation["end"] > len(lines):
        row.update({"state": BROKEN, "because": BECAUSE_PAST_EOF,
                    "why": "line %d is past end-of-file (%d lines)"
                           % (citation["end"], len(lines))})
        return row
    if not citation["symbol"]:
        # NOT CHECKED, AND SAID SO. The line exists; nothing claims anything
        # about it.
        row.update({"state": UNVERIFIABLE, "because": BECAUSE_NO_SYMBOL,
                    "why": "the citation carries no symbol (%s), so there is "
                           "nothing to check on line %d"
                           % (citation["symbol_from"], citation["start"])})
        return row
    span = lines[citation["start"] - 1:citation["end"]]
    if any(_on_line(citation["symbol"], line) for line in span):
        row.update({"state": OK, "because": BECAUSE_SYMBOL_ON_LINE,
                    "why": "%r is on %s"
                           % (citation["symbol"],
                              "line %d" % citation["start"]
                              if citation["start"] == citation["end"]
                              else "lines %d-%d" % (citation["start"],
                                                    citation["end"]))})
        return row
    elsewhere = _lines_holding(citation["symbol"], lines)
    if elsewhere:
        row.update({"state": MOVED, "because": BECAUSE_SYMBOL_ELSEWHERE,
                    "found_at": elsewhere,
                    "why": "%r is NOT on %s - it is on %s"
                           % (citation["symbol"],
                              "line %d" % citation["start"]
                              if citation["start"] == citation["end"]
                              else "lines %d-%d" % (citation["start"],
                                                    citation["end"]),
                              ", ".join(str(n) for n in elsewhere[:8]))})
        return row
    row.update({"state": BROKEN, "because": BECAUSE_SYMBOL_ABSENT,
                "why": "%r is not on the cited line and not anywhere in the "
                       "file" % (citation["symbol"],)})
    return row


def check_text(text, sources=None):
    return [check_one(c, sources=sources) for c in citations_in(text)]


def totals(rows):
    out = {state: 0 for state in STATES}
    for row in rows:
        out[row["state"]] = out.get(row["state"], 0) + 1
    return out


def verdict(rows):
    """(exit code, sentence). Never a tick, and never silent about nothing."""
    counts = totals(rows)
    if not rows:
        # A CHECKER THAT FINDS NOTHING REPORTS CLEAN. So finding nothing is
        # itself a failure: either the document has no citations or the
        # extractor is broken, and those two must not look alike.
        return 2, ("NO CITATION WAS FOUND AT ALL. Either this document cites "
                   "nothing or the extractor is broken, and a checker that "
                   "finds nothing always reports clean")
    bad = sum(counts[s] for s in FAILING)
    parts = ", ".join("%s %d" % (s.lower(), counts[s]) for s in STATES)
    if bad:
        return 1, ("NOT VERIFIED: %d of %d citations cannot be trusted (%s)"
                   % (bad, len(rows), parts))
    if counts[UNVERIFIABLE]:
        return 0, ("NO BROKEN OR MOVED CITATION, and %d of %d are "
                   "UNVERIFIABLE - they carry no symbol, so they were not "
                   "checked. This document is NOT verified (%s)"
                   % (counts[UNVERIFIABLE], len(rows), parts))
    return 0, ("every one of %d citations is OK (%s)" % (len(rows), parts))


# ------------------------------------------------------------- the controls
#
# FOUR FIXTURES AND FOUR BLINDINGS. The brief asked for the four fixtures and
# for one blinding - "make the symbol comparison always succeed" - and that
# single blinding CANNOT redden three of them: a missing file is still
# missing however the comparison answers, and a citation with no symbol never
# reaches a comparison. Measured, not argued: see `blindings()`.
#
# So each state gets the blinding that could actually hide it, which is this
# estate's own rule - a control must observe the guard it tests, or a
# different guard answers first and the control passes while blind.

_FIXTURE_FILE = "src/fixture_control.py"
_FIXTURE_LINES = [
    "def first_control_function():",
    "    return 1",
    "",
    "THE_CONTROL_SYMBOL = 'planted'",
    "",
    "def last_control_function():",
    "    return 2",
]

#: EACH FIXTURE OBSERVES (state, which guard answered). The second half is
#: not decoration - see the BECAUSE_* block for the measurement that made it
#: necessary.
_FIXTURES = (
    ("OK: a correct citation",
     "`%s:4` `THE_CONTROL_SYMBOL`" % _FIXTURE_FILE,
     (OK, BECAUSE_SYMBOL_ON_LINE)),
    ("MOVED: a citation one line off",
     "`%s:5` `THE_CONTROL_SYMBOL`" % _FIXTURE_FILE,
     (MOVED, BECAUSE_SYMBOL_ELSEWHERE)),
    ("BROKEN: a citation into a file that is not there",
     "`src/deleted_control.py:4` `THE_CONTROL_SYMBOL`",
     (BROKEN, BECAUSE_NO_FILE)),
    ("BROKEN: a line past end-of-file",
     "`%s:9001` `THE_CONTROL_SYMBOL`" % _FIXTURE_FILE,
     (BROKEN, BECAUSE_PAST_EOF)),
    ("UNVERIFIABLE: a bare citation with no symbol",
     "| `%s:4` |" % _FIXTURE_FILE, (UNVERIFIABLE, BECAUSE_NO_SYMBOL)),
    ("REFUSED: a citation outside the boundary",
     "`src/providers/bison.py:822` `PAGE_CAP`", (REFUSED, BECAUSE_BOUNDARY)),
)


def _planted_sources(path):
    if path == _FIXTURE_FILE:
        return list(_FIXTURE_LINES), "planted fixture, %d lines" % len(
            _FIXTURE_LINES)
    bad, why = forbidden(path)
    if bad:
        raise Refused(why)
    raise FileNotFoundError("no %s in the planted fixture set" % path)


def _fixture_states(sources=None):
    out = []
    for label, markdown, expected in _FIXTURES:
        rows = check_text(markdown, sources=sources or _planted_sources)
        observed = ((rows[0]["state"], rows[0].get("because")) if rows
                    else ("NO CITATION EXTRACTED", None))
        out.append({"control": label, "planted": markdown,
                    "expected": expected, "observed": observed,
                    "ok": observed == expected,
                    "detail": rows[0].get("why") if rows else None,
                    "found_at": rows[0].get("found_at") if rows else None})
    return out


def blindings():
    """Each weakening, and which control it reddens. MEASURED.

    This is the half that proves the four fixtures are watching four
    different guards rather than one.
    """
    import contextlib

    out = []
    # THE MODULE'S OWN NAMESPACE, not `sys.modules[__name__]`. This file is
    # loaded through `importlib` by its test module, under a private name
    # that is never registered in `sys.modules` - so the lookup raised
    # KeyError inside the suite while working from the command line, and the
    # blindings were being proven in the one place nothing watches.
    namespace = globals()

    @contextlib.contextmanager
    def swapped(name, value):
        previous = namespace[name]
        namespace[name] = value
        try:
            yield
        finally:
            namespace[name] = previous

    def always_on_line(symbol, line):
        return True

    def missing_is_empty(path):
        try:
            return _planted_sources(path)
        except FileNotFoundError:
            return [""] * 999, "planted: a missing file read as empty"

    # BOUND BEFORE THE SWAP. `citations_in` looks `symbol_near` up as a
    # global, which is what makes the blinding work at all - and it is also
    # why a blinding that calls `symbol_near` by name calls ITSELF. Measured:
    # 990 frames of recursion on the first run of this control.
    real_symbol_near = symbol_near

    def no_symbol_is_checked(text, after):
        found, how = real_symbol_near(text, after)
        return (found or "THE_CONTROL_SYMBOL"), how

    def extract_nothing(text):
        return []

    # ONE BLINDING PER GUARD, and the expected-red column is a MEASUREMENT
    # of which fixture each one can reach. The brief asked for a single
    # blinding - "make the symbol comparison always succeed" - and asked that
    # it redden three fixtures. It cannot: a missing file is still missing
    # however the comparison answers, and a citation with no symbol never
    # reaches a comparison at all. So each state gets the weakening that
    # could actually hide it.
    #
    # The `BROKEN` pair is the interesting one: `missing_is_empty` reddens
    # the no-file fixture and NOT the past-EOF fixture, because 999 planted
    # empty lines contain line 9001 nowhere either. Both are BROKEN and they
    # are different guards.
    plan = (
        ("the symbol comparison always succeeds", "_on_line", always_on_line,
         (MOVED,)),
        ("a missing file is read as empty", None, missing_is_empty,
         (BROKEN,)),
        ("a citation with no symbol is treated as checked", "symbol_near",
         no_symbol_is_checked, (UNVERIFIABLE,)),
        ("the extractor finds nothing", "citations_in", extract_nothing,
         (OK, MOVED, BROKEN, BROKEN, UNVERIFIABLE, REFUSED)),
    )
    for label, attribute, value, expected_red in plan:
        if attribute is None:
            rows = _fixture_states(sources=value)
        else:
            with swapped(attribute, value):
                rows = _fixture_states()
        red = tuple(r["expected"][0] for r in rows if not r["ok"])
        out.append({"blinding": label, "expected_red": expected_red,
                    "observed_red": red, "ok": red == expected_red})
    return out


def self_test(out=print):
    """The four fixtures, the fifth, and the four blindings. All printed."""
    fixtures = _fixture_states()
    out("")
    out("CONTROLS - six planted citations, and each observes WHICH GUARD "
        "answered")
    for row in fixtures:
        out("  %-4s %-48s expected %-13s observed %s"
            % ("OK" if row["ok"] else "FAIL", row["control"][:48],
               row["expected"][0], row["observed"][0]))
        out("       because: expected %r observed %r"
            % (row["expected"][1], row["observed"][1]))
        out("       planted: %s" % row["planted"])
        if row["detail"]:
            out("       %s" % row["detail"][:150])
    weak = blindings()
    out("")
    out("AND EACH ONE PROVEN ABLE TO FAIL - one blinding per guard, because")
    out("the symbol comparison cannot hide a missing file or an absent symbol")
    for row in weak:
        out("  %-4s %-52s expected red %-28s observed red %s"
            % ("OK" if row["ok"] else "FAIL", row["blinding"][:52],
               ",".join(row["expected_red"]),
               ",".join(row["observed_red"]) or "NOTHING"))
    held = all(r["ok"] for r in fixtures) and all(r["ok"] for r in weak)
    out("")
    out("  %d of %d controls hold; %d of %d blindings redden exactly the "
        "control they should"
        % (sum(1 for r in fixtures if r["ok"]), len(fixtures),
           sum(1 for r in weak if r["ok"]), len(weak)))
    return 0 if held else 2


def report(path, rows, out=print):
    code, sentence = verdict(rows)
    out("")
    out("%s" % path)
    for row in rows:
        out("  %-13s %s:%s%s   (%s)"
            % (row["state"], row["path"], row["start"],
               "" if row["start"] == row["end"] else "-%d" % row["end"],
               row.get("because")))
        out("       cited on line %d of the document; symbol %r (%s)"
            % (row["cited_in_line"], row["symbol"], row["symbol_from"]))
        out("       %s" % row["why"])
        if row.get("note"):
            out("       %s" % row["note"])
    counts = totals(rows)
    prefix = [r for r in rows if r["state"] == BROKEN and r.get("resolves_to")]
    out("  TOTALS  " + "  ".join("%s=%d" % (s, counts[s]) for s in STATES))
    if prefix:
        # SAID SEPARATELY, because the two are different work: one is a
        # wrong claim, the other is a path a reader cannot paste.
        out("          of the %d BROKEN, %d are a citation whose directory "
            "was omitted and which resolves to exactly one file"
            % (counts[BROKEN], len(prefix)))
    out("  %s" % sentence)
    return code


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("files", nargs="*", help="markdown files to check")
    ap.add_argument("--self-test", action="store_true",
                    help="run the planted controls and the blindings")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    if args.self_test:
        return self_test()
    if not args.files:
        ap.error("name at least one markdown file, or use --self-test")

    worst, payload = 0, {}
    for path in args.files:
        try:
            with open(path, encoding="utf-8") as handle:
                text = handle.read()
        except OSError as exc:
            print("ERROR  %s could not be read: %s" % (path, exc))
            worst = max(worst, 2)
            continue
        rows = check_text(text)
        payload[path] = {"rows": rows, "totals": totals(rows),
                         "verdict": verdict(rows)[1]}
        if args.json:
            worst = max(worst, verdict(rows)[0])
        else:
            worst = max(worst, report(path, rows))
    if args.json:
        print(json.dumps(payload, indent=1, default=str))
    return worst


if __name__ == "__main__":
    raise SystemExit(main())
