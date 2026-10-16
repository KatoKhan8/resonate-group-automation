# TASK-0120 -- THE WIDENED READER RULE: text specification + implementation.
#
# CONTEXT (0090's finding).  TASK-0075's clearing rule (as encoded in
# .codex/0080/classify.py) reads a verdict row's OWN clause only.  On the
# foreign corpus (LANE-pilotcaps.md) most UNKNOWN verdicts are not missing
# evidence -- the evidence is recorded in forms the rule cannot read:
#   (i)  one line BELOW the verdict row, in the same indented block (the
#        AssertionError under a kill-set row; the FAIL rows under a suite
#        tally), or in a kill-reason block behind a pointer line;
#   (ii) stated as a COUNT ("KILLED (3)", "CAUGHT by 2", "failures=2") or a
#        control label, with the names on the subordinate lines.
# This module re-reads the SAME records (both extractors imported UNCHANGED)
# with a widened EVIDENCE reader.  It is a scratch instrument for TASK-0120
# and lands nowhere outside the lane branch.
#
# ============================ THE RULE, AS TEXT ============================
# W0  VERDICT LAYER UNCHANGED.  Which lines are records, and each record's
#     outcome (kill / survive / stale-only), come from the strict extractor
#     byte-identically.  The widening adds EVIDENCE paths only.  A row with
#     no verdict is not gradeable, however much evidence sits near it, and
#     no widened path may change a record's outcome.
# W1  EVIDENCE BLOCK.  For a record whose unit span ends at line E with row
#     indent I, the evidence block is the contiguous run of lines after E
#     where every line is indented >= I and is NOT:
#       - blank (block ends),
#       - a strong unit head (markdown header, bullet, numbered item, table
#         row, **bold-lead** paragraph, or flush prose when I > 0),
#       - a line carrying outcome or stale vocabulary (the block ends
#         BEFORE it: a verdict line is never evidence -- this is what keeps
#         a SURVIVED row that follows a KILLED row out of its block),
#     capped at 8 lines.  A RESULT ROW also ends the block: a line carrying
#     a test_ name and ending in a bare (unquoted) GREEN/RED cell records a
#     DIFFERENT test's verdict (measured at L10487; bare GREEN is not
#     extractor vocabulary -- this is a boundary rule and can only refuse).
#     Over row-span + block, the reader accepts the
#     SAME fact vocabularies the strict rule reads -- SIGNATURES,
#     SIZE_CHANGE_CLAIM, SECOND_CLEARING, PYC_PRECAUTION, LOADPROOF_CLEAR,
#     and NAME with one RECALL FIX: the char class gains A-Z, because
#     test_..._is_NOT_MET_... was harvested TRUNCATED at the first capital
#     (a grammar artifact, not evidence; 0090 made the same class of fix
#     for '_').  No other new vocabulary exists in this module.
# W2a COUNT CERTIFICATION.  A kill row stating a count N -- "KILLED (N)",
#     "KILLED by N", "CAUGHT by N", "failures=N", "-> N red", "N red", a
#     non-empty kill-set with N members, or a block line "exactly N of" --
#     certifies completeness: the widened name list must hold exactly N
#     distinct names.  Count != names => the widening REFUSES (the row
#     stays UNKNOWN and the refusal is printed with both numbers).
# W2b KILL-REASON BLOCK (pointer form).  A pointer line within 14 lines
#     below the row ("for the intended reason", "kill-reasons", "captured
#     rather than assumed"), followed within 4 lines by an indented run of
#     signature lines, attaches those signatures to the kill row -- but
#     ONLY when the row stated a count N AND exactly N signature lines are
#     found AND exactly N names were certified under W2a.  Without a count
#     the pointer form is refused (the pairing is then unverifiable).
# W3  WIDENED GRADING (clearing paths only):
#       AFFECTED -- exactly as the strict rule.  The stale path is NOT
#         widened: doctrine-vs-demonstration is a judgment a block form
#         cannot support, and classify_facts still runs FIRST on the
#         unchanged facts, so every strict SAFE/AFFECTED verdict stands.
#       SAFE -- (strict rule says SAFE) OR, for outcome=kill: names AND a
#         signature found over row+block (W1), with W2a/W2b certification
#         whenever a count or pointer is present; for outcome=survive: a
#         clearing fact (size change / whole-second / pyc precaution /
#         load-proof -- the same vocabularies) found over row+block.
#       UNKNOWN -- everything else, fail-closed, with the strict reason
#         plus what the widened reader looked for and did not find.
#     The proof standard is unchanged: a red is cleared only by a NAMED
#     killing agent with a STATED signature (attribution), or by a
#     staleness-defeating fact; a survivor only by a staleness-defeating
#     fact.  What widened is WHERE the rule looks, not WHAT it demands.
# ==========================================================================
import re
import sys

sys.path.insert(0, r"C:\Users\Zvonimir\Desktop\wt-glm-review-2026-10-14\.codex\0090")
sys.path.insert(0, r"C:\Users\Zvonimir\Desktop\wt-glm-review-2026-10-14\.codex\0080")

import extract_pilotcaps as _ep           # noqa: E402  foreign extractor, UNCHANGED
from classify import classify_facts       # noqa: E402  UNCHANGED

# W1 vocabularies: the strict module's own patterns, imported, not re-typed.
SIGNATURE_PATTERNS = _ep.SIGNATURES
SIZE_CHANGE_CLAIM = _ep.SIZE_CHANGE_CLAIM
SECOND_CLEARING = _ep.SECOND_CLEARING
PYC_PRECAUTION = _ep.PYC_PRECAUTION
LOADPROOF_CLEAR = _ep.LOADPROOF_CLEAR
OUTCOME_VOCAB = _ep.KILL + _ep.SURVIVE
STALE_VOCAB = [p for _, p in _ep.STALE_MARKERS]

# W1 recall fix: capitals admitted into the name tail (strict class
# truncates 'test_..._is_NOT_MET_...' at the first capital).
NAME_W = re.compile(r'\btest_[A-Za-z0-9_]{8,}\b')

# W2a count forms, as measured in the corpus readback.
COUNT_FORMS = [
    re.compile(r'\bKILLED \((\d+)\)'),
    re.compile(r'\bKILLED by (\d+)'),
    re.compile(r'\bCAUGHT by (\d+)'),
    re.compile(r'failures=(\d+)'),
    re.compile(r'-> (\d+) red'),
    re.compile(r'\b(\d+) red\b'),
    re.compile(r'exactly (\d+) of\b'),
]
KILLSET_COUNT = re.compile(r'kill-set\s*=?\s*[\[{]([^\]};]{1,90})[\]}]')

# W2b pointer + signature-run forms.
POINTER = re.compile(
    r'for the intended reason|kill-reasons?|captured rather than assumed')

# W1 stop: a RESULT ROW -- a line carrying a test_ name and ending in a bare
# (unquoted) GREEN/RED cell -- records a DIFFERENT test's verdict and ends
# the evidence block.  Measured at L10487 ('test_c1_..._is_MET   GREEN'),
# which would otherwise donate a third name to L10480's certified count of
# 2.  Bare GREEN is not SURVIVE vocab, so the strict extractor correctly
# ignores such lines; this is a block-boundary rule only, and it can only
# REFUSE (end evidence earlier), never clear.  Backticked commentary like
# L16149's "the other 3 stayed `ok`" is not a result row and stays readable.
RESULT_ROW_STOP = re.compile(
    r'test_[A-Za-z0-9_]{8,}.{0,40}\s(?:GREEN|RED)\s*$')

BLOCK_CAP = 8
POINTER_WINDOW = 14
POINTER_GAP = 4


def _indent(line):
    return len(line) - len(line.lstrip(" "))


def _has_vocab(line):
    flat = " ".join(line.split())
    return (any(p.search(flat) for p in OUTCOME_VOCAB)
            or any(p.search(flat) for p in STALE_VOCAB)
            or bool(RESULT_ROW_STOP.search(line)))


def _is_strong_head(line):
    s = line.strip()
    if not s:
        return False
    if _indent(line) == 0:
        return True                      # flush prose/row ends any block
    return bool(re.match(r'^#{1,6} |^[-*] |^\d+[a-z]?\. |^\||^\*\*[^*]+\*\*', s))


def evidence_block(lines, span_end, row_indent):
    """W1: contiguous lines below the record's span, indent >= row indent,
    stopping at blanks, strong heads, cap -- and BEFORE any verdict line."""
    block = []
    k = span_end                          # 0-based index AFTER the span
    while k < len(lines) and len(block) < BLOCK_CAP:
        ln = lines[k]
        if not ln.strip():
            break
        if _indent(ln) < row_indent:
            break
        if _is_strong_head(ln):
            break
        if _has_vocab(ln):
            break                         # a verdict line is never evidence
        block.append((k + 1, ln))         # 1-based line number
        k += 1
    return block


def _signatures_of(text):
    return [name for name, p in SIGNATURE_PATTERNS if p.search(text)]


def _counts_of(text):
    out = []
    for p in COUNT_FORMS:
        out += [int(m) for m in p.findall(text)]
    for m in KILLSET_COUNT.finditer(text):
        members = [x.strip() for x in m.group(1).split(",") if x.strip()]
        out.append(len(members))
    return out


def killreason_signatures(lines, row_line):
    """W2b: pointer within POINTER_WINDOW lines below the row, then an
    indented run of signature lines within POINTER_GAP lines.  Returns the
    signature line texts (may be empty)."""
    best = None
    for k in range(row_line, min(row_line + POINTER_WINDOW, len(lines))):
        if POINTER.search(lines[k]):
            best = k
            break
    if best is None:
        return []
    run = []
    for k in range(best + 1, min(best + 1 + POINTER_GAP + BLOCK_CAP,
                                 len(lines))):
        ln = lines[k]
        if not ln.strip():
            if run:
                break                     # run already started: blank ends it
            continue                      # blank before the run: keep looking
        if _indent(ln) < 2:
            if run:
                break
            continue
        if _has_vocab(ln):
            break
        if _signatures_of(ln):
            run.append(ln)
        elif run:
            break
    return run


def widen_record(rec, lines):
    """Re-read ONE strict record under W1/W2a/W2b.  Returns a dict with the
    strict verdict (unchanged), the widened verdict, and the clause that
    fired / the reason nothing did."""
    row_line0 = rec["line"] - 1
    span_end = rec["end_line"]            # 0-based index after the span
    row_indent = _indent(lines[row_line0])
    span_text = "\n".join(lines[row_line0:span_end])
    block = evidence_block(lines, span_end, row_indent)
    block_text = "\n".join(t for _, t in block)
    wide_text = span_text + "\n" + block_text

    strict_v, strict_reason, _ = classify_facts(rec)
    out = {"line": rec["line"], "strict": strict_v, "reason_strict":
           strict_reason, "block": [n for n, _ in block], "clause": None,
           "wide": strict_v, "reason_wide": strict_reason}

    # W0/W3: AFFECTED and SAFE strict verdicts stand; the stale path is not
    # widened, so nothing can demote and AFFECTED cannot be reached newly.
    if strict_v != "UNKNOWN":
        return out

    if rec["outcome"] == "kill":
        names = sorted(set(NAME_W.findall(wide_text)))
        sigs = _signatures_of(wide_text)
        counts = sorted(set(_counts_of(span_text + " " + block_text)))
        kr = killreason_signatures(lines, rec["line"])
        clause, why_not = None, []
        if kr and counts:
            sigs = sorted(set(sigs) | set(_signatures_of("\n".join(kr))))
        if not names:
            why_not.append("no name over row+block (W1)")
        if not sigs:
            why_not.append("no signature over row+block (W1/W2b)")
        if names and sigs:
            if counts:
                if len(names) not in counts:
                    why_not.append(
                        "W2a REFUSED: count %s vs %d names"
                        % (counts, len(names)))
                elif kr and len(kr) not in counts:
                    why_not.append(
                        "W2b REFUSED: %d kill-reason lines vs count %s"
                        % (len(kr), counts))
                else:
                    clause = ("W1 named-reason kill, count-certified"
                              + (" + W2b kill-reason block" if kr else ""))
            else:
                clause = "W1 named-reason kill (no count stated)"
        if clause:
            out["wide"] = "SAFE"
            out["clause"] = clause
            out["reason_wide"] = (
                "%s -- %d name(s), signature '%s'%s"
                % (clause, len(names), sigs[0],
                   (", count %d certified" % len(names)
                    if counts and len(names) in counts else "")))
        else:
            out["reason_wide"] = "; ".join(why_not)
        return out

    if rec["outcome"] == "survive":
        facts = []
        if SIZE_CHANGE_CLAIM.search(wide_text):
            facts.append("size change")
        if SECOND_CLEARING.search(wide_text):
            facts.append("whole-second difference")
        if PYC_PRECAUTION.search(wide_text):
            facts.append("pyc precaution")
        if LOADPROOF_CLEAR.search(wide_text):
            facts.append("load-proof")
        if facts:
            out["wide"] = "SAFE"
            out["clause"] = "W1 survivor clearing fact: " + ", ".join(facts)
            out["reason_wide"] = out["clause"]
        else:
            out["reason_wide"] = ("survivor verdict; no clearing fact over "
                                  "row+block (W1)")
        return out

    # stale-only records: no widened path (W3 -- the stale path is not
    # widened, and a clearing path cannot attach to a stale-only record).
    out["reason_wide"] = "stale-only record; widening does not apply"
    return out


def widen_corpus(records, text):
    lines = [ln.rstrip("\r") for ln in text.split("\n")]
    return [widen_record(r, lines) for r in records]
