# TASK-0090 -- Layer 1 for a FOREIGN corpus: LANE-pilotcaps.md.
#
# A copy of .codex/0080/extract.py (same ';'-clause discipline, same
# whitespace normalisation, same fail-closed fact model) with a
# DOCUMENTED, minimal dialect extension set: every delta below names the
# pilotcaps form it reads and the rule concept it serves.  Nothing here
# touches a verdict -- .codex/0080/classify.py is imported UNCHANGED and
# every verdict in this task comes from that byte-identical file.
#
# DELTAS vs 0080/extract.py:
#
#  unit grammar
#   U1  BOLD_LEAD: a flush paragraph opening with a **bold lead** is a unit.
#       pilotcaps states record results in bold-led prose where glm used
#       bullets ("**M4 was UNKILLED on the first pass** --", "**20
#       MUTATIONS, EVERY ONE KILLED BY A NAMED TEST**,").  Same concept as
#       BULLET: one structured unit, one record.  Outcome vocabulary still
#       gates, so bold prose without a verdict is not a record.
#   U2  INDENT rows: pilotcaps' verdict tables are 4-space indented
#       monospace blocks.  A line indented 4-7 spaces starts a row-unit;
#       a line indented 8+ spaces is a CONTINUATION of that row, because
#       pilotcaps puts the kill-set / test names on the wrapped tail of
#       its plant row (TASK-0245 P1/P2, TASK-0234 X1-B2).
#   U3  the single-plant merge takes ANY same-line, same-outcome clause
#       pair: pilotcaps tells one plant's result across several clauses
#       inside one row, and its row labels (P1, M4, X1, C4a) are not the
#       **P1**/**Plant E** shapes 0080's SINGLE_PLANT regex was tuned to.
#   U4  entry facts are SECTION-scoped, not TASK-scoped: pilotcaps entries
#       are long multi-section documents, and a pyc protocol stated in one
#       section (0253 section 7) must not clear kill records made in
#       another (0253 section 4).  Facts propagate from the record's own
#       '##'/'###' segment only -- strictly fail-closed: a protocol stated
#       outside the segment does not clear, which can only under-clear.
#
#  outcome vocabulary
#   V1  KILL += 'CAUGHT' (0080 has lowercase 'caught' only), lowercase
#       'killed by', '-> <cell/count/name> red', non-empty 'kill-set {...}',
#       '**YES**' / '**no**' (the PC0252 boundary-test columns).  Readback
#       correction to an earlier note: those two cell forms also fire on 8
#       barrier-prospect rows (L862-L872, L1178) and one fixture row
#       (L15248) that are not kill verdicts; the patterns are kept for the
#       genuine PC0252 products L19513/L19514 and those rows are excluded
#       per line in run_0090.EXCLUSIONS.
#   V2  SURVIVE += 'UNKILLED', 'NOBODY SAW IT', 'kill-set EMPTY',
#       'survives', 'loses (its|the) red' (a control that stops catching).
#   V3  C4-style rows state BOTH the kill-set and the survivor-set in one
#       row ("KILLED {...} survived {...}"): the kill is the outcome and
#       the survivor list is collateral, so 'survived {...}' tails are
#       stripped before SURVIVE matching -- else the both-vocab rule sends
#       the row to unparsed.  This mirrors 0080's single-plant merge,
#       which exists for exactly this one-result-told-in-parts shape.
#
#  stale markers (rule concept: AFFECTED)
#   S1  += 'pyc-reused-across-mutations' -- "Python reused M6's
#       __pycache__ for M7" (TASK-0235's M6/M7 incident): a recorded
#       demonstration that a verdict came from the previous mutant's
#       cached bytecode.  Deliberately NARROW: the lesson sentence "a
#       harness that lets the interpreter cache is measuring the previous
#       mutation" is NOT a marker -- it is doctrine, not a demonstration,
#       and marking it would misread TASK-0236's precaution record as
#       AFFECTED (classify checks stale before every clearing fact).
#
#  clearing facts
#   F1  PYC_PRECAUTION += PYTHONDONTWRITEBYTECODE / dont_write_bytecode /
#       '__pycache__' unlinked|absent / backticked '-B' -- disjunct (d)
#       "in its recorded form": pilotcaps records the same precaution in
#       its own vocabulary (qwen/0176 precedent, per 0080's own comment).
#   F2  LOADPROOF += pilotcaps' own form, "All N load-proofs passed" and
#       the getsource-marker assertion -- same rule concept as 0080's
#       'load-proof CLEAN'.  Recorded at SECTION level in this corpus (one
#       paragraph covering every plant of the section), so the fact is
#       propagated to records like entry-level size change is in 0080;
#       every propagated hit is hand-verified in the readback.
#   F3  SIZE vocab unchanged: pilotcaps writes '+49 B' / '+17 B', which
#       SIZE_CHANGE_CLAIM already reads.
#
#  deliberately NOT extended (measured boundaries, reported not patched):
#   NAME stays test_[a-z0-9_]+ -- pilotcaps kill-sets whose members are
#       criterion labels (C2, C2b, C1.P1) or unprefixed snake names do
#       not name a test in the rule's grammar.
#   SECOND_CLEARING unchanged; no pilotcaps form of it was found.
#   'VOID ... reported as VOID rather than as a survivor', 'stay green,
#       as required' and bare restoration rows are not made records: they
#       have no outcome vocabulary the rule recognises.  Named in the
#       report as the corpus' own verdict words the rule cannot read.
import re
import sys

# ---------------------------------------------------------------- unit scoping
BULLET = re.compile(r'^\s*[-*] ')
NUMBERED = re.compile(r'^\s*\d+[a-z]?\. ')
TABLE = re.compile(r'^\s*\|')
PROSE_EXCEPT = re.compile(r'^\s*\*\*Mutation proof\*\*:')
BOLD_LEAD = re.compile(r'^\*\*[^*\n]{1,120}\*\*')          # U1
INDENT_ROW = re.compile(r'^ {4,7}\S')                       # U2
INDENT_CONT = re.compile(r'^ {8,}\S')                       # U2
UNIT = re.compile('|'.join(p.pattern for p in
                          (BULLET, NUMBERED, TABLE, PROSE_EXCEPT,
                           BOLD_LEAD, INDENT_ROW)))

LEADS = [re.compile(p) for p in (
    r'Mutations\b', r'Mutation:', r'Mutation proof', r'Mutation-proven')]

# ------------------------------------------------------- outcome vocabulary
KILL = [re.compile(p) for p in (
    # ---- 0080's list, unchanged -------------------------------------------
    r'\bRED\b ?[:,(]',
    r'\*\*FAIL\*\*',
    r'\bfail(?:s|ed|ing)? on exactly\b',
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
    # ---- V1: pilotcaps forms ----------------------------------------------
    r'\bCAUGHT\b',                 # "CAUGHT by 2", "CAUGHT - newly red:"
    r'\bkilled by\b',              # "every one killed by a named test"
    r'-> [A-Za-z0-9_]+ red\b',     # "-> C4 red", "-> 3 red"; also a test
                                   # name before 'red' (0231's re-run table
                                   # L9503 -- readback recall patch: '_' was
                                   # not in the class, so a genuine named-kill
                                   # row was not a record at all)
    r'kill-set\s*=?\s*[\[{][^\]};]{1,90}[\]}]',  # non-empty kill-set,
                                   # "{...}", "= {...}" and "= [...]" forms
                                   # (readback-verified misses L15449/L15451/
                                   # L16148; empty {} stays commentary)
    r'\*\*YES\*\*',                # PC0252 boundary column
    r'\*\*no\*\*',                 # PC0252 boundary column (MB1)
)]
SURVIVE = [re.compile(p) for p in (
    # ---- 0080's list, unchanged -------------------------------------------
    r'mutation → green',
    r'mutation -> green',
    r'\*\*SURVIVED\*\*',
    r'\bSURVIVED\b',
    r'kill-set ∅',
    # ---- V2: pilotcaps forms ----------------------------------------------
    r'\bUNKILLED\b',
    r'NOBODY SAW IT',
    r'kill-set EMPTY',
    r'\bsurvives\b',
    r'loses (?:its|the) red',
)]

# V3: "KILLED {...} survived {...}" rows -- the survivor set is collateral.
SURVIVOR_SET_TAIL = re.compile(r'\bsurvived \{[^}]*\}')

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
    # ---- S1: TASK-0235's M6/M7 incident ------------------------------------
    ('pyc-reused-across-mutations', re.compile(
        r'reused [^.;\n]{0,24}?__pycache__')),
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
    ('quoted-failure-string', re.compile(
        r"string in the failure")),
    ('outside-perform-failure', re.compile(
        r'was called OUTSIDE')),
]

# ------------------------------------------------------------------- size facts
SIZE_CHANGE_CLAIM = re.compile(
    r'[+−-]\d+\s?(?:B\b|bytes\b)|changed the file size|'
    r'the size change(?: alone)? invalidated')
SIZE_SAME_CLAIM = re.compile(
    r'same[- ]size|BYTE-LENGTH IDENTICAL|size \d+ before AND after|'
    r'\d+ B unchanged|\d+ bytes both|size-identical')
ENTRY_SIZE_CHANGE = re.compile(
    r'[Ee]ach mutation changed the file size')

# ------------------------------------------------- timing / precaution / revert
SECOND_CLEARING = re.compile(
    r'different whole second|strictly later whole second|'
    r'whole second provably differing|'
    r'header recompiled|forced a recompile|'
    r'the timestamp field alone invalidated')
LOADPROOF_CLEAR = re.compile(r'load-proof CLEAN|\| CLEAN \|')
# F2: pilotcaps' own load-proof form, recorded once per section.
SECTION_LOADPROOF = re.compile(
    r'load-proofs? [^.;\n]{0,80}?passed|'
    r'load-proof[^.;\n]{0,120}?inspect\.getsource')
PYC_PRECAUTION = re.compile(
    # ---- F1: pilotcaps' recorded forms first, then 0080's list ------------
    r'PYTHONDONTWRITEBYTECODE|dont_write_bytecode|`-B`|'
    r'__pycache__[^.;\n]{0,120}?(?:unlinked|absent)|'
    r'unlinked[^.;\n]{0,120}?__pycache__|'
    # ---- 0080's list -------------------------------------------------------
    r'__pycache__[^.;\n]{0,120}?(?:deleted|dropped|removed)|'
    r'(?:deleted|dropped|removed)[^.;\n]{0,120}?__pycache__|'
    r'delete the pyc')
REVERT_CLAIM = re.compile(
    r'Revert sha-EQUAL|sha256-equal|restored|git checkout|'
    r'git hash-object|pre-plant bytes|byte round-trip|'
    r'revert sha256 IDENTICAL|sha256 IDENTICAL')
NOT_IN_PLACE = re.compile(
    r'two trees differ|cross-tree|the simulated fix')

TRANSFORM = re.compile(r'->|→|swapped for|swapped in|replaced by')
NAME = re.compile(r'\btest_[a-z0-9_]+')

MAX_SPAN = 30  # wrapped-unit continuation cap, in lines


def _derive_size(flat):
    """Byte-length delta when the clause quotes BOTH sides of the mutation
    verbatim around a transform marker -- 0080's arithmetic, unchanged."""
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
            continue
        return len(a.encode()), len(b.encode()), a, b
    return None


def parse(text):
    lines = text.split("\n")
    records, unparsed = [], []

    # U4: section segmentation at BOTH '##' and '###'.  Section-level facts
    # govern every record inside that section -- and only that section.
    sections = []          # (start_line0, end_line0, section_id, facts)
    cur = None
    for idx, ln in enumerate(lines):
        if re.match(r'^#{2,3} ', ln):
            if cur:
                cur[1] = idx
                sections.append(cur)
            cur = [idx, len(lines), ln.lstrip('#').strip()[:60], None]
    if cur:
        sections.append(cur)
    for s in sections:
        body = "\n".join(lines[s[0]:s[1]])
        s[3] = {
            "section_pyc_precaution": bool(PYC_PRECAUTION.search(body)),
            "section_size_change": bool(ENTRY_SIZE_CHANGE.search(body)),
            "section_not_in_place": bool(NOT_IN_PLACE.search(body)),
            "section_loadproof": bool(SECTION_LOADPROOF.search(body)),
        }

    def section_facts(line0):
        for s in sections:
            if s[0] <= line0 < s[1]:
                return s[2], s[3]
        return "(frontmatter)", {"section_pyc_precaution": False,
                                 "section_size_change": False,
                                 "section_not_in_place": False,
                                 "section_loadproof": False}

    def is_unit(i):
        # U2: an 8+-space line continues the row above, never starts one.
        if i < len(lines) and INDENT_CONT.match(lines[i]):
            return False
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
            # V3: the survivor-set tail is collateral on a kill row.
            flat_live = SURVIVOR_SET_TAIL.sub(" ", flat)
            kill = any(p.search(flat) for p in KILL)
            survive = any(p.search(flat_live) for p in SURVIVE)
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
            sid, sf = section_facts(start)
            rec = {
                "line": start + 1, "end_line": j, "section": sid,
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
            rec.update(sf)
            # F2 / U4: section-level load-proof and pyc precaution reach the
            # record through the fields classify.py actually reads.
            if sf["section_loadproof"]:
                rec["loadproof_clear"] = True
            if sf["section_pyc_precaution"]:
                rec["pyc_precaution_local"] = True
            # classify.py reads entry_size_change / entry_pyc_precaution /
            # entry_not_in_place -- feed the section facts through them.
            rec["entry_size_change"] = sf["section_size_change"]
            rec["entry_pyc_precaution"] = sf["section_pyc_precaution"]
            rec["entry_not_in_place"] = sf["section_not_in_place"]
            if kill and survive:
                rec["unparsed"] = "clause matches both survivor and kill vocabulary"
                unparsed.append(rec)
            else:
                records.append(rec)
        i = j

    # U3: merge same-line, same-outcome clause records (one plant, one row).
    merged = []
    for rec in records:
        prev = next((m for m in merged
                     if m["line"] == rec["line"]), None)
        if prev and prev["outcome"] == rec["outcome"]:
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
        print("L%-5d %-28s %-10s %-8s %-14s %-14s %s" % (
            r["line"], r["section"][:26], r["outcome"],
            ",".join(r["names"])[:18] or "-",
            r["signature"] or "-",
            r["size_change"] or "-", r["excerpt"][:56]))
    print("-- %d records, %d unparsed" % (len(recs), len(unp)))
