# TASK-0078 -- section 3 instrument: a census of the MUTATION RESULTS
# recorded in a lane file, classifying each by whether its kill-set names a
# test.  Read-only over the lane file's own bytes; re-runs nothing.
#
# What counts as a record (and what deliberately does not):
#   - A record is a STRUCTURED unit only: a bullet ("- " / "* "), a numbered
#     item ("12. " / "3a. "), a table row, or a line opening
#     "**Mutation proof**:".  Prose paragraphs and section headers are never
#     records, even when they summarise mutations -- a summary is not a
#     result (that is what keeps "C1, paired, ... kill-set `∅`" and the
#     "Mutation-proven in three states" lead-in out of the denominator).
#   - A unit becomes a record when a clause of it carries outcome
#     vocabulary.  Clauses are ';'-separated segments, because several
#     entries record several results in one bullet (B4, B7).
#   - When a unit contains a results-announcing lead phrase ("Mutations",
#     "Mutation:", "Mutation proof", "Mutation-proven" -- capital M), only
#     the text AFTER the lead can hold records: the text before it is the
#     surrounding test-file description, whose born-RED markers are standing
#     test state, not mutation results.
#   - NAMED: the clause contains >= 1 `test_[a-z0-9_]+` token -- this
#     estate's unittest naming convention.  Names hyphen-broken across
#     wrapped lines match as fragments by design; that is recorded in the
#     census, not papered over.
#   - UNNAMED: outcome parsed, zero test_ tokens -- including explicit
#     empty kill-sets ("kill-set ∅").  That is the census's subject.
#   - UNPARSED (fail-closed): a clause matching BOTH survivor and kill
#     vocabulary.  UNPARSED is never counted as NAMED.  A "Killed N" count
#     claim with no parsable name is NOT unparsed -- the outcome is fully
#     classified (kill, count N); the kill-set is described rather than
#     named, which is the census's subject, so it is UNNAMED (0074's
#     Plant E: "Killed 4, BOTH directions: the floor-fixture test ... both
#     classifier tests").
#
# Vocabulary matching runs on the clause with whitespace normalised: this
# file wraps prose at ~95 columns, and a vocabulary phrase wrapped across a
# line break is still that phrase (found on L1539, whose "fix absent → red"
# occupies two lines and anchored nothing until normalised).
#
# Vocabulary is deliberately specific: "Revert -> green" is a REVERT, not a
# survivor, so survivor needs "mutation -> green" / "**SURVIVED**" /
# "kill-set ∅"; bare "RED" only counts when it opens an account
# (RED:, RED,, RED() as the 0063 items write it, not "4 RED markers").
import re
import sys

BULLET = re.compile(r'^\s*[-*] ')
NUMBERED = re.compile(r'^\s*\d+[a-z]?\. ')
TABLE = re.compile(r'^\s*\|')
PROSE_EXCEPT = re.compile(r'^\s*\*\*Mutation proof\*\*:')
UNIT = re.compile(r'|'.join(p.pattern for p in (BULLET, NUMBERED, TABLE, PROSE_EXCEPT)))

LEADS = [re.compile(p) for p in (
    r'Mutations\b', r'Mutation:', r'Mutation proof', r'Mutation-proven')]

KILL = [re.compile(p) for p in (
    r'\bRED\b[:,(]',
    r'\bred naming\b',
    r'\bKill:\s',
    r'Killed(?: EXACTLY)? \d',
    r'-> \d+ failures?',
    r'→ \d+ failures?',
    r'\bFAILED\b',
    r'\*\*KILLED\*\*',
    r'unexpected success',
    r'UNEXPECTED SUCCESS',
    r'self-destruct',
    r'\bcaught\b',
    r'fires the change-detector',
    r'still red',
    r'fix absent → red',
    r'red and green',
)]

SURVIVE = [re.compile(p) for p in (
    r'mutation → green',
    r'mutation -> green',
    r'\*\*SURVIVED\*\*',
    r'kill-set ∅',
)]

NAME = re.compile(r'\btest_[a-z0-9_]+')

MAX_SPAN = 30  # wrapped-bullet continuation cap, in lines


def parse(text):
    lines = text.split("\n")
    records, unparsed = [], []

    def is_unit(i):
        return (i < len(lines)
                and (UNIT.search(lines[i]) or (lines[i].strip() == "")))

    i = 0
    while i < len(lines):
        if not UNIT.search(lines[i]):
            i += 1
            continue
        start = i
        j = i + 1
        while j < len(lines) and j - start < MAX_SPAN and not is_unit(j):
            j += 1
        span_text = "\n".join(lines[start:j])
        # A lead phrase scopes records to the text after it.
        candidate = span_text
        for lead in LEADS:
            m = lead.search(span_text)
            if m:
                candidate = span_text[m.start():]
                break
        for clause in candidate.split(";"):
            flat = " ".join(clause.split())
            kill = any(p.search(flat) for p in KILL)
            survive = any(p.search(flat) for p in SURVIVE)
            if not (kill or survive):
                continue
            names = sorted(set(NAME.findall(flat)))
            rec = {"line": start + 1, "end_line": j,
                   "excerpt": flat[:100],
                   "outcome": ("survive" if survive else "kill"),
                   "names": names}
            if kill and survive:
                rec["verdict"] = "UNPARSED"
                rec["why"] = "clause matches both survivor and kill vocabulary"
                unparsed.append(rec)
            else:
                rec["verdict"] = "NAMED" if names else "UNNAMED"
                records.append(rec)
        i = j
    return records, unparsed


def census(path):
    with open(path, "rb") as fh:
        text = fh.read().decode("utf-8")
    records, unparsed = parse(text)
    named = [r for r in records if r["verdict"] == "NAMED"]
    unnamed = [r for r in records if r["verdict"] == "UNNAMED"]
    survivors_unnamed = [r for r in unnamed if r["outcome"] == "survive"]
    return {"records": records, "unparsed": unparsed,
            "total": len(records),
            "named": len(named), "unnamed": len(unnamed),
            "unnamed_survivors": len(survivors_unnamed),
            "named_list": named, "unnamed_list": unnamed}


def report(path):
    c = census(path)
    print("census of %s" % path)
    print("denominator: %d mutation-result records" % c["total"])
    print()
    for r in c["records"]:
        print("L%-5d %-7s %-8s %s" % (r["line"], r["verdict"], r["outcome"],
                                      r["excerpt"]))
        if r["names"]:
            print("       names: %s" % ", ".join(r["names"]))
    print()
    print("NAMED %d / UNNAMED %d of %d; unnamed-with-survive-outcome %d"
          % (c["named"], c["unnamed"], c["total"], c["unnamed_survivors"]))
    if c["unparsed"]:
        print("UNPARSED %d (excluded from the denominator):" % len(c["unparsed"]))
        for r in c["unparsed"]:
            print("L%-5d %s -- %s" % (r["line"], r["why"], r["excerpt"]))
    else:
        print("UNPARSED 0")
    return c


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    report(sys.argv[1])
