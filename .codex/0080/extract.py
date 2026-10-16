# TASK-0080 -- Layer 1: extract every mutation-proof RECORD from a lane file,
# with the facts TASK-0075's clearing rule needs.  Adapted from
# .codex/0078/parse_lane.py (same unit scoping, same lead-phrase rule, same
# clause splitting, same whitespace normalisation); what changed is that a
# record now carries FACTS (names, stated signature, size claims, timing
# claims, pyc precautions, revert method, stale-proof markers) instead of only
# a NAMED/UNNAMED verdict, and that a clause carrying an explicit stale-proof
# marker is a record even without outcome vocabulary (0078's section-2 bullets
# record a verdict-void demonstration, not a kill/survive word).
#
# The scoping decisions that keep qwen/0176's failure mode out:
#   - a record is a STRUCTURED unit (bullet, numbered item, table row,
#     "**Mutation proof**:" line).  Prose paragraphs, headings, and
#     "## VERIFICATION" commentary are never records, however much mutation
#     vocabulary they summarise.  A summary is not a result.
#   - clauses are ';'-separated segments of the unit's post-lead text.
#   - outcome vocabulary runs on the whitespace-normalised clause, because
#     this file wraps at ~95 columns.
#
# Recorded facts, and where each may come from:
#   names            clause-local `test_[a-z0-9_]+` tokens ONLY.  A name in a
#                    neighbouring clause or a paragraph above is NOT carried
#                    by the record; that strictness is deliberate (fail
#                    closed) and its cost is measured by C3.
#   signature        a stated failure signature in the clause (the assertion
#                    text, a "not raised" refusal, a KeyError, the wrong
#                    label received, ...).  Described-but-unnamed kills are
#                    exactly what this separates from named-reason kills.
#   size_change      'change-claim'  the clause STATES the byte length moved
#                                     ("+10 B", "changed the file size")
#                    'same-claim'    the clause states SAME size (annotates
#                                     the hazard shape; never clears)
#                    'change-derived' both the original and the mutant are
#                                     quoted verbatim either side of a
#                                     transform marker and differ in byte
#                                     length -- the delta is arithmetic on
#                                     two recorded strings, not a guess.
#                                     Elided mutants ("...") derive nothing.
#   second_clearing  the clause records a whole-second difference that
#                    invalidated the pyc header (plant mtime in a different
#                    whole second, revert in a strictly later one).
#   pyc_precaution   clause-local OR entry-level recorded __pycache__
#                    deletion between plant and run.
#   stale_marker     an explicit stale-bytecode demonstration in the clause
#                    (0075 P3, 0078's plant leg, 0079's table cells).
#   not_in_place     entry-level: the "mutation" is a cross-tree differential
#                    or fixture-level simulation, so no module was written in
#                    place and no reload event exists to be stale.
import re
import sys

# ---------------------------------------------------------------- unit scoping
BULLET = re.compile(r'^\s*[-*] ')
NUMBERED = re.compile(r'^\s*\d+[a-z]?\. ')
TABLE = re.compile(r'^\s*\|')
PROSE_EXCEPT = re.compile(r'^\s*\*\*Mutation proof\*\*:')
UNIT = re.compile('|'.join(p.pattern for p in
                           (BULLET, NUMBERED, TABLE, PROSE_EXCEPT)))

LEADS = [re.compile(p) for p in (
    r'Mutations\b', r'Mutation:', r'Mutation proof', r'Mutation-proven')]

# ------------------------------------------------------------ entry scoping
ENTRY = re.compile(r'^## (.+)$')

# ------------------------------------------------------- outcome vocabulary
KILL = [re.compile(p) for p in (
    r'\bRED\b ?[:,(]',      # optional space: 0060 #4 writes "RED (ERROR):"
    r'\*\*FAIL\*\*',        # 0065 records a unittest run as "**FAIL**, ..."
    r'\bfail(?:s|ed|ing)? on exactly\b',  # 0072 re-dispatch: "both fail on
                                         # exactly the invariant"
    r'\bred naming\b',
    r'\bKill:\s',
    r'Killed(?: EXACTLY)? \d',
    r'-> \d+ failures?',
    r'→ \d+ failures?',
    r'\bFAILED\b',
    r'\*\*KILLED\*\*',
    r'\bKILLED\b',
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
    r'\bSURVIVED\b',
    r'kill-set ∅',
)]

# A clause carrying one of these is a record even with no kill/survive word:
# the entry is demonstrating a forged verdict, which is a mutation result.
STALE_MARKERS = [
    ('stale-bytecode-verdict', re.compile(
        r'STALE BYTECODE')),
    ('stale-original-imported', re.compile(
        r'stale original bytecode|imported the stale')),
    ('behaved-as-original', re.compile(
        r'behaved as the ORIGINAL|answered with the pre-plant')),
    ('header-would-reuse', re.compile(
        r'header-would-reuse-stale-bytes: True')),
]

# ------------------------------------------------------------------ signatures
SIGNATURES = [
    ('assertion-error', re.compile(
        r'AssertionError[^\n;,]{0,100}')),
    ('key-error', re.compile(
        r'\bKeyError[^\n;,]{0,80}')),
    ('exc-name', re.compile(
        r'\b(?:ActionRefused|WriteRefused|StopRefused|FactoryRefused|'
        r'ProviderWriteRefused|BudgetExceeded|UnpricedCall|StopRefused)'
        r'\b[^\n;,]{0,60}')),
    ('not-raised', re.compile(r'\bnot raised\b')),
    ('none-not', re.compile(
        r'is not None|None is not true|!= 497')),
    ('escaped-handler', re.compile(
        r'escap(?:es|ed|ing) the handler')),
    ('vanished', re.compile(r'\bvanished\b')),
    ('got-wrong-label', re.compile(r'\(got "')),
    ('named-assertion', re.compile(
        r'fails (?:its|the) `[^`\n]{1,80}` assertion')),
    ('refusal-never-came', re.compile(r'refusal never came')),
    ('quoted-failure-text', re.compile(
        r"refusal text = |' not found in|not found in '")),
    ('budget-exceeded-not-raised', re.compile(
        r'BudgetExceeded not raised')),
    ('quoted-failure-string', re.compile(   # 0030: "the guard's own string
        r"string in the failure")),         # in the failure: *\"...\"*"
    ('outside-perform-failure', re.compile(  # 0072's invariant message,
        r'was called OUTSIDE')),             # quoted verbatim
]

# ------------------------------------------------------------------- size facts
SIZE_CHANGE_CLAIM = re.compile(
    r'[+−-]\d+\s?(?:B\b|bytes\b)|changed the file size|'
    r'the size change(?: alone)? invalidated')
SIZE_SAME_CLAIM = re.compile(
    r'same[- ]size|BYTE-LENGTH IDENTICAL|size \d+ before AND after|'
    r'\d+ B unchanged|\d+ bytes both|size-identical')
# Entry-level: a claim that covers EVERY mutation in the entry.
ENTRY_SIZE_CHANGE = re.compile(
    r'[Ee]ach mutation changed the file size')

# ------------------------------------------------- timing / precaution / revert
SECOND_CLEARING = re.compile(
    r'different whole second|strictly later whole second|'
    r'whole second provably differing|'   # 0079 R3's own remedy description
    r'header recompiled|forced a recompile|'
    r'the timestamp field alone invalidated')
# A recorded load-proof CLEAN (0078's instrument) -- stronger than the pyc
# precaution it replaces: the module object was PROVEN equal to disk bytes at
# verdict time.  Table form is a bare "| CLEAN |" cell (0079 section 2).
LOADPROOF_CLEAR = re.compile(r'load-proof CLEAN|\| CLEAN \|')
PYC_PRECAUTION = re.compile(
    r'__pycache__[^.;\n]{0,120}?(?:deleted|dropped|removed)|'
    r'(?:deleted|dropped|removed)[^.;\n]{0,120}?__pycache__|'
    r'delete the pyc')
REVERT_CLAIM = re.compile(
    r'Revert sha-EQUAL|sha256-equal|restored|git checkout|'
    r'git hash-object|pre-plant bytes|byte round-trip')
NOT_IN_PLACE = re.compile(
    # 'the simulated fix' -- 0030: the delta between red and green is a
    # scope opened in the test fixture, so no module was ever written.
    r'two trees differ|cross-tree|the simulated fix')

TRANSFORM = re.compile(r'->|→|swapped for|swapped in|replaced by')
NAME = re.compile(r'\btest_[a-z0-9_]+')

MAX_SPAN = 30  # wrapped-bullet continuation cap, in lines


def _derive_size(flat):
    """Byte-length delta when the clause quotes BOTH sides of the mutation
    verbatim around a transform marker.  The nearest backtick tokens either
    side of the marker, within a 30-char window (keeps '-> 6 failures, ...
    `no_composed_step`' from pairing), only ASCII strings (an elided mutant
    like `if False and …` proves nothing), and both tokens must carry
    whitespace -- a code-snippet shape.  0077's re-dispatch rows put
    `working sha256 <hex>` -> `FAILED (failures=1)` around the marker; a sha
    token has no space, so the shape test rejects that mispair."""
    for m in TRANSFORM.finditer(flat):
        left = flat[:m.start()]
        right = flat[m.end():]
        lt = re.findall(r'`([^`]+)`', left[-120:])
        rt = re.findall(r'`([^`]+)`', right[:30])
        if not (lt and rt):
            continue
        a, b = lt[-1], rt[0]
        if not (a.isascii() and b.isascii()):
            continue
        if not (any(c.isspace() for c in a) and any(c.isspace() for c in b)):
            continue  # identifier/hash token, not a two-sided code snippet
        return len(a.encode()), len(b.encode()), a, b
    return None


def parse(text):
    lines = text.split("\n")
    records, unparsed = [], []

    # entry segmentation first: entry-level facts govern every record inside
    entries = []          # (start_line0, end_line0, entry_id, entry_facts)
    cur = None
    for idx, ln in enumerate(lines):
        m = ENTRY.match(ln)
        if m:
            if cur:
                cur[1] = idx
                entries.append(cur)
            cur = [idx, len(lines), m.group(1).strip()[:60], None]
    if cur:
        entries.append(cur)
    for e in entries:
        body = "\n".join(lines[e[0]:e[1]])
        e[3] = {
            "entry_pyc_precaution": bool(PYC_PRECAUTION.search(body)),
            "entry_size_change": bool(ENTRY_SIZE_CHANGE.search(body)),
            "entry_not_in_place": bool(NOT_IN_PLACE.search(body)),
        }

    def entry_facts(line0):
        for e in entries:
            if e[0] <= line0 < e[1]:
                return e[2], e[3]
        return "(frontmatter)", {"entry_pyc_precaution": False,
                                 "entry_size_change": False,
                                 "entry_not_in_place": False}

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
        candidate = span_text
        for lead in LEADS:
            m = lead.search(span_text)
            if m:
                candidate = span_text[m.start():]
                break
        for clause in candidate.split(";"):
            flat = " ".join(clause.split())
            if not flat:
                continue
            kill = any(p.search(flat) for p in KILL)
            survive = any(p.search(flat) for p in SURVIVE)
            stale = next((name for name, p in STALE_MARKERS
                          if p.search(flat)), None)
            if not (kill or survive or stale):
                continue
            names = sorted(set(NAME.findall(flat)))
            signature = next((name for name, p in SIGNATURES
                              if p.search(flat)), None)
            size = None
            delta = None
            if SIZE_CHANGE_CLAIM.search(flat):
                size = "change-claim"
            elif SIZE_SAME_CLAIM.search(flat):
                size = "same-claim"
            derived = _derive_size(flat)
            if derived is not None:
                la, lb, a, b = derived
                delta = lb - la
                if delta != 0 and size is None:
                    size = "change-derived"
                elif delta == 0 and size is None:
                    size = "same-derived"
            eid, ef = entry_facts(start)
            rec = {
                "line": start + 1, "end_line": j, "entry": eid,
                "excerpt": flat[:110],
                "outcome": ("survive" if survive else
                            "kill" if kill else "stale-only"),
                "names": names,
                "signature": signature,
                "size_change": size,
                "derived_delta": delta,
                "second_clearing": bool(SECOND_CLEARING.search(flat)),
                "loadproof_clear": bool(LOADPROOF_CLEAR.search(flat)),
                "pyc_precaution_local": bool(PYC_PRECAUTION.search(flat)),
                "revert_claim": bool(REVERT_CLAIM.search(flat)),
                "stale_marker": stale,
            }
            rec.update(ef)
            if kill and survive:
                rec["unparsed"] = "clause matches both survivor and kill vocabulary"
                unparsed.append(rec)
            else:
                records.append(rec)
        i = j

    # A unit headed by ONE plant label ("**P1, ...**", "**Plant E ...**",
    # "**M1 ...**") holds one result told in several ';'-clauses (0075 P1's
    # narrative splits its run, verdict and revert across clauses) -- merge
    # those into one record.  Multi-plant units ("**Mutations**:", B4/B7)
    # keep clause-level records: their clauses are distinct plants.
    SINGLE_PLANT = re.compile(
        r'^\s*[-*]?\s*\*\*(?:P\d\b|Plant [A-F]\b|M\d)')
    merged = []
    for rec in records:
        prev = next((m for m in merged
                     if m["line"] == rec["line"]), None)
        if (prev and SINGLE_PLANT.match(lines[rec["line"] - 1])
                and prev["outcome"] == rec["outcome"]):
            prev["names"] = sorted(set(prev["names"]) | set(rec["names"]))
            for k in ("signature", "size_change", "derived_delta",
                      "second_clearing", "loadproof_clear",
                      "pyc_precaution_local", "revert_claim", "stale_marker"):
                if prev[k] in (None, False) and rec[k] not in (None, False):
                    prev[k] = rec[k]
        else:
            merged.append(rec)
    return merged, unparsed


def extract(path):
    with open(path, "rb") as fh:
        text = fh.read().decode("utf-8")
    return parse(text)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    recs, unp = extract(sys.argv[1])
    for r in recs:
        print("L%-5d %-10s %-8s %-12s %-14s %-8s %s" % (
            r["line"], r["entry"][:10], r["outcome"],
            ",".join(r["names"])[:12] or "-",
            r["signature"] or "-",
            r["size_change"] or "-", r["excerpt"][:60]))
    print("-- %d records, %d unparsed" % (len(recs), len(unp)))
