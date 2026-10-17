#!/usr/bin/env python3
"""Does this baseline's provenance block describe the file it sits in?

ADVISORY AND UNWIRED, deliberately. Nothing in CI calls this file, and in
this lineage nothing in CI exists to call it: `.github/workflows/suite.yml`
and `.github/suite-baseline.txt` are absent here, born on branches this
lineage does not contain. `read_baseline` in `scripts/ci_suite.py` skips
every `#` line, so where a workflow does run the gate, a provenance block is
never read by it. This is the reader that was missing. Whether it is ever
wired into a workflow is the operator's decision and is NOT made here.

Every question is answered and printed, including after one of them has
already failed, because the reader needs the whole picture rather than the
first `False`:

    a   is there a provenance block at all?
    b   does its `SHA` resolve to a commit in this repository?
    c1  is that commit an ancestor of the tip that carries this file?
    c2  is that commit an ancestor of origin/master?  (printed, NOT judged)
    f   does the block say it was carried forward rather than measured?
    d   does `failures` + `errors`, MINUS the collapse the block declares,
        equal the number of names the file lists?
    e   how many names does the file list, re-parsed here, and does the
        `# names:` header agree with that?

THE TWO SIDES OF (d) ARE DIFFERENT UNITS, AND THE BLOCK DECLARES THE BRIDGE.
`failures=` and `errors=` are the runner's own counts of EVENTS - one per
closing-summary line - while this file lists NAMES. One test can print more
than one closing line: a parameterised `subTest` prints one per iteration, and
`_parse_failures` keys every one of them by the dotted path, so N iterations
become one name. Nothing in this file can tell the reader how far the event
count exceeds the name count, so the block states it in a `collapsed` field
(name, integer, first token of the value) and (d) subtracts it. A block that
declares no `collapsed` field is judged as declaring zero - the check stays
ARMED on every block that has not stated its units, and the printed line says
so rather than defaulting quietly.

MEASURED, 2026-10-17, on branch task-merge-0280-units-reconcile-2026-10-17:
the committed block's `runner` line is the verbatim runner output and its
arithmetic is honest in events. X2-offline-suite_run.log has 265 closing
lines (172 FAIL + 93 ERROR), `_parse_failures` keys them to 261 names, and the
file lists exactly those 261 - both directions empty. The gap is the one
subTest at `test_the_lead_carries_one_subject_and_a_body_per_step`, whose five
iterations `(steps=2)`..`(steps=6)` all FAILED: 5 events, 1 name, 4 absorbed,
265 - 4 = 261, residual 0. The X1-plain run of the same clone at the same SHA
shows the same shape (271 events, 267 names, 4 absorbed), so (d) as it stood
before this change could not pass on EITHER measured run - a check that is red
on every honest input carries no information.

VERDICT VOCABULARY, first match wins:

    NO-PROVENANCE             no block, so there is nothing to trust
    STALE-UNRESOLVED:<sha>    the declared SHA is not a commit here
    STALE:not-an-ancestor-of-tip
                              the commit exists but this file's lineage is
                              not built on it
    STALE:inherited           the block describes an earlier file, so how
                              good its arithmetic looks proves nothing
    MISMATCH:<names>!=<names> the arithmetic does not close, compared in NAME
                              units: the event total less the declared
                              collapse, against the names this file lists
    VALID                     all of the above hold
    UNKNOWN:<what>            an authority could not be read. Never a pass -
                              an unreadable authority is UNKNOWN, and UNKNOWN
                              is not zero and not safe.

    WHAT (d) STILL CANNOT SEE, named rather than implied: a block that
    declares a `collapsed` it did not measure is internally consistent. This
    reader reads a FILE, not the log the block names, so it can only test the
    block against itself. That ceiling is unchanged by the units repair; what
    the repair removes is a check that was red on every honest input.

WHY c2 IS PRINTED AND NOT JUDGED. A block whose SHA is not an ancestor of
origin/master was measured on a lineage master does not contain, which is a
real finding - but it is not the same question as "does this block describe
this file". On the committed block the two disagree: the declared SHA IS an
ancestor of every one of the tips that carry the file and is NOT an ancestor of
origin/master. If c2 gated the verdict, that block would read STALE and the
units question (172 + 93 = 265 events against 261 names) would stay invisible
behind it. The verdict answers (a) (b) (c1) (f) (d); (c2) is reported as a
WARN and left to a human.

HOW (a) FINDS THE BLOCK. (a) asked "is there a provenance block at all?"
with a case-folded SUBSTRING over `#` lines - `PROVENANCE in line.upper()` - so
it answered "does this line MENTION the word". A blockless file whose header
said it carried no provenance block therefore read as carrying one, and because
the block the reader invented declares no `SHA`, the verdict was
`STALE-UNRESOLVED:` - a stale SHA nothing had declared. Measured 2026-10-17:
found on merge/0280, which reported it and did not repair it; repaired on
merge/0300. (a) now matches an ANCHORED MARKER - `#`, whitespace, the word, and
a boundary or the end of the line - so the marker is the comment rather than a
word inside it. The block's other end was already structural and is unchanged:
the marker opens it and it runs to the last `#` line before the first name, so
the extent is bounded by the file's own shape and not by a word.

WHAT THIS DID NOT CHANGE, said plainly so nobody reads a repair as a rescue:
BOTH answers exit 3, so this never flipped a gate and nothing unsafe was ever
let through. It moved the DIAGNOSIS - from "no block, so there is nothing to
trust" to a stale SHA the reader had invented - and the diagnosis is the part a
human acts on.

THE POPULATION, MEASURED 2026-10-17 RATHER THAN ASSUMED. This docstring said
"all four tips"; there are more. 1181 refs, of which 62 carry this file, over
36 distinct tips - and all 36 read MISMATCH before this change and VALID after
it. Four was the set that had been named, not the set that exists, which is how
a denominator shrinks without anyone deciding it should.

Exit 0 only for VALID. Any other verdict exits 3; a usage error or a
repository git cannot be asked about exits 2.
"""
import argparse
import hashlib
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
#: The block's opening marker, ANCHORED: `#`, whitespace, the word,
#: then a boundary or the end of the line. This replaced
#: `"PROVENANCE" in line.upper()`, which answered "does this comment
#: mention the word" and so read prose as a block. See the docstring:
#: the marker is the comment, not a word that happens to sit in it.
BLOCK_OPENS = re.compile(r"^#\s*PROVENANCE(?=[\s.,:!?]|$)")
#: `ci_suite.regen_baseline` writes this line when it carries a block
#: forward instead of measuring one. A STRICT SUBSET of BLOCK_OPENS,
#: so (a) needs no separate test for it; it is kept as the reader's
#: mirror of the writer's own label, and nothing in this file reads
#: it.
CARRIED = re.compile(r"^#\s*PROVENANCE CARRIED FORWARD")
FIELD = re.compile(r"^#\s+(\S+)\s{2,}(\S.*)$")
COUNT_HEADER = re.compile(r"^#\s*(names|reported|logs)\s*:\s*(\d+)\s*$")
RUNNER = re.compile(r"failures=(\d+)")
ERRORS = re.compile(r"errors=(\d+)")
#: The leading integer of the `collapsed` field: how many EVENT lines the
#: runner's counts put on a name this file already lists. See the docstring -
#: the two sides of (d) are different units and this is the declared bridge.
COLLAPSED = re.compile(r"(\d+)")
# Only these keys are fields. A line that matches FIELD with any other key is
# prose that happens to be indented, and the real block is full of it (the
# `where` field's continuation lines are three of them). Recording them as
# parsed fields would invent data; counting them as unparsed says what is true.
FIELD_KEYS = ("measured", "sha", "where", "how", "log", "runner", "collapsed",
              "inherited")


def git(args, repo):
    """(returncode, stdout, stderr) from git, with the GIT_CONFIG_COUNT family
    cleared: an inherited GIT_CONFIG_COUNT with no matching KEY_/VALUE_ pair
    makes every git call in this shell fail, which is a property of the caller
    and not of the repository. Decoding is pinned to utf-8 because text=True
    alone decodes with the console codepage."""
    env = {k: v for k, v in os.environ.items()
           if k != "GIT_CONFIG_COUNT"
           and not k.startswith("GIT_CONFIG_KEY_")
           and not k.startswith("GIT_CONFIG_VALUE_")}
    p = subprocess.run(["git"] + list(args), cwd=repo, env=env,
                       capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "").strip(), (p.stderr or "").strip()


def parse(path):
    """What the file says. Never raises for a bad file - an unreadable file is
    reported as absent, and absence is a verdict rather than an exception."""
    out = {"exists": os.path.exists(path), "bytes": None, "sha256": None,
           "cr": 0, "total_lines": 0, "block": None, "block_at": None,
           "fields": {}, "unparsed": 0, "header": {}, "names": [],
           "name_lines": 0}
    if not out["exists"]:
        return out
    with open(path, "rb") as fh:
        raw = fh.read()
    out["bytes"] = len(raw)
    out["sha256"] = hashlib.sha256(raw).hexdigest()
    out["cr"] = raw.count(b"\r")
    # splitlines() is the CR-tolerant reader: CRLF, LF and a lone CR all split
    # the same, so a checkout that flipped line endings cannot make the block
    # parse differently from the blob.
    lines = raw.decode("utf-8", errors="replace").splitlines()
    out["total_lines"] = len(lines)

    names, block, block_at, seen_names = [], [], None, False
    for i, line in enumerate(lines):
        if line.startswith("#"):
            if block_at is not None and not seen_names:
                block.append(line)
            elif block_at is None and not seen_names and BLOCK_OPENS.match(line):
                block_at, block = i + 1, [line]
            continue
        if line.strip():
            seen_names = True
            names.append(line.strip())
    out["block"], out["block_at"] = block or None, block_at
    out["names"], out["name_lines"] = names, len(names)

    for line in block or []:
        m = FIELD.match(line)
        if m and m.group(1).lower() in FIELD_KEYS:
            out["fields"][m.group(1).lower()] = m.group(2).strip()
        elif COUNT_HEADER.match(line) or line.strip() == "#":
            pass
        else:
            out["unparsed"] += 1
    for line in lines:
        m = COUNT_HEADER.match(line)
        if m:
            out["header"][m.group(1)] = int(m.group(2))
    return out


def ancestry(repo, sha, rev):
    """(answer, detail) for `sha` is-an-ancestor-of `rev`. Three states, not
    two: git exits 1 for NO and 128 for "I could not tell you", and a run that
    reads those as the same answer has invented a measurement."""
    rc, out, err = git(["merge-base", "--is-ancestor", sha, rev], repo)
    if rc == 0:
        return True, "yes"
    if rc == 1:
        return False, "no"
    return None, f"git exit {rc}: {err.splitlines()[0] if err else 'no stderr'}"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--tip", default="HEAD",
                    help="the commit that carries this file (default HEAD)")
    ap.add_argument("--master-ref", default="origin/master",
                    help="the ref c2 asks about (default origin/master)")
    ap.add_argument("--repo", default=ROOT)
    args = ap.parse_args(argv)

    def say(label, text):
        print(f"{label:<10} {text}")

    say("file", args.baseline)
    rc, _out, err = git(["rev-parse", "--git-dir"], args.repo)
    if rc != 0:
        # Fail closed: with no readable repository, (b) (c1) and (c2) are all
        # UNKNOWN, and UNKNOWN never becomes VALID.
        say("repo", f"UNREADABLE at {args.repo}: {err.splitlines()[0] if err else 'no stderr'}")
        say("VERDICT", "UNKNOWN:repo-unreadable")
        return 2

    p = parse(args.baseline)
    if not p["exists"]:
        say("read", "ABSENT - no file, so no block, so no provenance")
        say("VERDICT", "NO-PROVENANCE")
        return 3

    say("read", f"{p['bytes']} byte(s)  sha256 {p['sha256'][:16]}...  "
                f"{p['total_lines']} line(s)  CR {p['cr']}  LF {p['total_lines']}")
    tip_rc, tip, tip_err = git(["rev-parse", args.tip], args.repo)
    if tip_rc != 0:
        say("tip", f"UNRESOLVED {args.tip}: {tip_err.splitlines()[0] if tip_err else 'no stderr'}")
        say("VERDICT", "UNKNOWN:tip-unreadable")
        return 3
    say("tip", f"{args.tip} -> {tip}")

    # (a) the block
    if p["block"] is None:
        say("check a", "block-present  NO - no anchored PROVENANCE marker")
        say("check b-e", "not run: with no block there is nothing to resolve")
        say("VERDICT", "NO-PROVENANCE")
        return 3
    say("check a", f"block-present  YES - at line {p['block_at']}, "
                   f"{len(p['block'])} line(s), {len(p['fields'])} field(s), "
                   f"{p['unparsed']} unparsed line(s)")
    for key in FIELD_KEYS:
        if key in p["fields"]:
            say("  field", f"{key:<9} {p['fields'][key]}")

    declared = p["fields"].get("sha", "")
    inherited = p["fields"].get("inherited", "").split(" ")[0].lower() in ("true", "yes", "1")

    # (b) does the declared SHA resolve, as a commit
    kind_rc, kind, _ = git(["cat-file", "-t", declared], args.repo) if declared else (1, "", "")
    resolves = kind_rc == 0 and kind == "commit"
    if not declared:
        say("check b", "sha-resolves  NO - the block declares no SHA")
    elif resolves:
        say("check b", f"sha-resolves  YES - {declared} is a {kind}")
    else:
        say("check b", f"sha-resolves  NO - `git cat-file -t {declared}` -> "
                       f"{kind or 'no output'}")

    # (c1) ancestor of the tip carrying the file, and (c2) of the master ref
    c1 = c2 = None
    if resolves:
        c1, c1_why = ancestry(args.repo, declared, tip)
        say("check c1", f"ancestor-of-tip  "
                        f"{'YES' if c1 else 'NO' if c1 is False else 'UNKNOWN'} - "
                        f"{declared} vs tip {tip} ({c1_why})")
    else:
        say("check c1", "ancestor-of-tip  not run: the SHA did not resolve")
    m_rc, master, m_err = git(["rev-parse", args.master_ref], args.repo)
    if not resolves:
        say("check c2", "ancestor-of-master  not run: the SHA did not resolve")
    elif m_rc != 0:
        say("check c2", f"ancestor-of-master  UNKNOWN - {args.master_ref} "
                        f"does not resolve here: {m_err.splitlines()[0] if m_err else ''}")
    else:
        c2, c2_why = ancestry(args.repo, declared, master)
        say("check c2", f"ancestor-of-master  "
                        f"{'YES' if c2 else 'NO' if c2 is False else 'UNKNOWN'} - "
                        f"{declared} vs {args.master_ref} {master} ({c2_why})")

    # (f) did the writer carry this block forward instead of measuring it?
    say("check f", f"inherited  {'YES - the block describes an earlier file' if inherited else 'no'}")

    # (d) the arithmetic, against (e) this parser's own count. Both sides are
    # put in NAME units before they are compared: the runner's event total
    # minus the collapse the block declares. With no `collapsed` field the
    # declared collapse is zero, which is the STRICTER reading and is said out
    # loud rather than defaulted quietly - a block that has not stated its
    # units does not get the benefit of the doubt.
    unique = sorted(set(p["names"]))
    runner_line = p["fields"].get("runner", "")
    collapsed_line = p["fields"].get("collapsed", "")
    f_m = RUNNER.search(runner_line or "")
    e_m = ERRORS.search(runner_line or "")
    c_m = COLLAPSED.match(collapsed_line or "")
    if f_m and e_m:
        total = int(f_m.group(1)) + int(e_m.group(1))
        collapsed = int(c_m.group(1)) if c_m else 0
        names_side = total - collapsed
        arith_ok = names_side == len(unique)
        bridge = (f"collapsed({collapsed})" if c_m else
                  "collapsed(0, no `collapsed` field declared)")
        say("check d", f"arithmetic  {'OK' if arith_ok else 'MISMATCH'} - "
                       f"failures({f_m.group(1)}) + errors({e_m.group(1)}) = {total} "
                       f"events - {bridge} = {names_side} name(s) "
                       f"vs parsed unique names {len(unique)}")
    else:
        arith_ok = False
        total = names_side = None
        say("check d", f"arithmetic  UNPARSED - runner line is "
                       f"{runner_line!r}; failures/errors not both present")

    # (e) the name count, re-parsed here, against the file's own header
    say("check e", f"names-parsed  {len(unique)} unique of {p['name_lines']} "
                   f"non-comment line(s)")
    if p["header"]:
        say("  header", " ".join(f"{k}={v}" for k, v in sorted(p["header"].items())))
        declared_names = p["header"].get("names")
        if declared_names is not None and declared_names != len(unique):
            say("WARN", f"the `# names:` header says {declared_names} and this "
                        f"parser counts {len(unique)}")

    if c2 is False:
        say("WARN", f"the declared SHA is NOT an ancestor of {args.master_ref}: "
                    f"these names were measured on a lineage master does not "
                    f"contain, which is a baseline-for-what question and is "
                    f"left to a human (see the module docstring)")

    # First match wins, in the order the checks are asked: (b) before (c1)
    # before (f) before (d). A block that fails (b) also fails (d) whenever its
    # arithmetic is stale, and reporting the arithmetic there would hide the
    # more basic fact that the SHA names no commit in this repository.
    if not resolves:
        verdict = f"STALE-UNRESOLVED:{declared}"
    elif c1 is False:
        verdict = "STALE:not-an-ancestor-of-tip"
    elif inherited:
        verdict = "STALE:inherited"
    elif not arith_ok:
        # The left-hand number is the NAME side, so the printed verdict is the
        # comparison the reader actually made and not the runner's raw event
        # count. With no declared collapse the two are the same number.
        verdict = (f"MISMATCH:"
                   f"{'unparsed' if names_side is None else names_side}"
                   f"!={len(unique)}")
    elif c2 is None:
        verdict = "UNKNOWN:master-ref-unreadable"
    else:
        verdict = "VALID"
    say("VERDICT", verdict)
    return 0 if verdict == "VALID" else 3


if __name__ == "__main__":
    raise SystemExit(main())