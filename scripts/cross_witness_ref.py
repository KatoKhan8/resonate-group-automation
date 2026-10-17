"""Cross-witness pin check - REFERENCE IMPLEMENTATION (qwen-coder/0220).

One implementation of the check adopted by qwen-coder/0190's verdict
(CROSS-WITNESS-SUFFICIENT), applying ALL FOUR adoption conditions at once:

  1. SECTION-ANCHORED PARSING, never whole-file. The lane document is parsed
     only between a start anchor (exactly one matching line, asserted, else
     REFUSE) and an end anchor or EOF. The end defaults to EOF because the
     re-pin protocol APPENDS a new entry after the pinned one, and the
     effective record must stay visible to the check.
  2. LINE-START canonical record pattern: a record line is machine-
     distinguishable from prose because it STARTS with
     '`<64-hex>` (pin recorded to '. Inside the anchored section, a line
     that carries the marker but is not a canonical record cannot be proven
     to be prose, and fails closed (UNPARSEABLE -> REFUSE).
  3. ENTRY-BEFORE-PIN ORDERING: the lane entry lands BEFORE the pin file is
     rewritten, so both interruption directions must REFUSE - a pin rewrite
     without a landed entry (measured == pin != lane) and a landed entry with
     a stale pin (measured == lane != pin). Requiring BOTH witnesses is that
     ordering made terminal-state-checkable; neither witness is ever trusted
     alone.
  4. ONE DIGEST PER MARKER LINE, LATEST WINS: a marker line carrying zero or
     two-or-more backticked 64-hex digests is UNPARSEABLE -> REFUSE, and the
     LAST record line in the anchored section carries the effective recorded
     digest (the lane file is append-only; landed entries are never edited in
     place), which makes every re-pin a visible, auditable lane event.

HONEST LIMIT, carried from the 0190 adoption verdict: BOTH WITNESSES ARE
AGENT-WRITABLE. The check converts silent concurrent mutation into an
auditable lane event; it is NOT a root of trust. A writer willing to fake the
lane record can still pass - that residual is covered by the append
protocol's prefix-sha assertion and by operator review of lane entries, not
by this check.

Verdict contract (0190's, unchanged): verdict in {ACCEPT, REFUSE, NEITHER}.
NEITHER only on unreadable input - a crash is never a verdict; every parse
problem is a fail-closed REFUSE, never a pass. Every REFUSE names the
disagreeing witness(es) or the unparseable line, with the values compared;
every ACCEPT prints all three values.

The four conditions are individually switchable keyword arguments (all
default True = the adopted behaviour) because the adoption brief requires
each condition to be PROVEN LOAD-BEARING by a mutation that removes exactly
one and moves at least one verdict. A False is a measurement instrument for
mutation runs and for tests/test_a_cross_witness_condition_removed_moves_a_
verdict.py; production callers must not pass one.
"""
import hashlib
import re

MARKER = "(pin recorded to"
DIGEST_RE = re.compile(r"`([0-9a-f]{64})`")
RECORD_RE = re.compile(r"^`([0-9a-f]{64})` \(pin recorded to(?:\s|$)")


def _sha256_file(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def cross_witness_check(instrument_path, pin_path, lane_path, log, anchor,
                        end_anchor=None, anchored=True, line_start=True,
                        both_witnesses=True, latest_wins=True):
    """Returns (verdict, detail, values).

    anchor / end_anchor are substrings identifying header lines in the lane
    document; each must occur on exactly one line (count==1 asserted, else
    REFUSE). The anchored section spans [anchor line, end-anchor line) or,
    when end_anchor is None, [anchor line, EOF). The lane document is opened
    READ-ONLY; pass a scratch copy if the live file must not be touched.
    """
    conditions = {"anchored": anchored, "line_start": line_start,
                  "both_witnesses": both_witnesses, "latest_wins": latest_wins}
    values = {"measured": None, "pin": None, "lane_effective": None,
              "lane_line": None, "record_lines": None, "marker_census": None,
              "section_start": None, "section_end": None,
              "lines_scanned": None, "lines_total": None,
              "conditions": conditions}
    try:
        values["measured"] = _sha256_file(instrument_path)
        with open(pin_path, "rb") as f:
            values["pin"] = f.read().decode("ascii").strip().lower()
        with open(lane_path, "rb") as f:
            lane_text = f.read().decode("utf-8")
    except Exception as e:  # unreadable input: a crash is never a verdict
        detail = "%s: %s" % (type(e).__name__, e)
        log("NEITHER: unreadable input: " + detail)
        return ("NEITHER", detail, values)

    lines = lane_text.split("\n")
    values["lines_total"] = len(lines)

    # ---- condition 1: section-anchored parsing, never whole-file ----------
    start, end = 0, len(lines)
    if anchored:
        ahits = [i for i, l in enumerate(lines) if anchor in l]
        if len(ahits) != 1:
            detail = ("lane witness UNPARSEABLE: anchor %r occurs on %d lines "
                      "(rule: exactly 1)" % (anchor, len(ahits)))
            log("REFUSE: " + detail)
            return ("REFUSE", detail, values)
        start = ahits[0]
        if end_anchor is not None:
            ehits = [i for i, l in enumerate(lines) if end_anchor in l]
            if len(ehits) != 1 or ehits[0] <= start:
                detail = ("lane witness UNPARSEABLE: end anchor %r occurs on "
                          "%d lines or not after the section start (rule: "
                          "exactly 1, after start)" % (end_anchor, len(ehits)))
                log("REFUSE: " + detail)
                return ("REFUSE", detail, values)
            end = ehits[0]
    values["section_start"] = start + 1  # 1-based document line
    values["section_end"] = end          # exclusive, 1-based document line
    section = lines[start:end]
    values["lines_scanned"] = len(section)

    # ---- conditions 2 + 4: canonical record lines, one digest each --------
    records = []  # (document line number, digest), in document order
    census = []   # every document line number containing the loose marker
    for off, line in enumerate(section):
        lineno = start + off + 1
        if MARKER not in line:
            continue
        census.append(lineno)
        if line_start and RECORD_RE.match(line) is None:
            detail = ("lane witness UNPARSEABLE: line %d carries the marker "
                      "but does not start with the canonical record pattern "
                      "'`<64-hex>` (pin recorded to '" % lineno)
            log("REFUSE: " + detail)
            return ("REFUSE", detail, values)
        digests = DIGEST_RE.findall(line)
        if len(digests) != 1:
            detail = ("lane witness UNPARSEABLE: marker line %d carries %d "
                      "backticked 64-hex digests (rule: exactly 1)"
                      % (lineno, len(digests)))
            log("REFUSE: " + detail)
            return ("REFUSE", detail, values)
        records.append((lineno, digests[0]))
    values["marker_census"] = census

    if not records:
        detail = ("lane witness MISSING: no canonical record line among the "
                  "%d scanned section lines" % len(section))
        log("REFUSE: " + detail)
        return ("REFUSE", detail, values)

    values["record_lines"] = [r[0] for r in records]
    # ---- condition 4 (second half): append-only lane, latest wins ---------
    eff_line, effective = records[-1] if latest_wins else records[0]
    values["lane_line"] = eff_line
    values["lane_effective"] = effective

    log("conditions   : anchored=%s line_start=%s both_witnesses=%s "
        "latest_wins=%s" % (anchored, line_start, both_witnesses, latest_wins))
    log("lane witness : section lines %d..%d (%d scanned of %d total) ; "
        "marker census %s ; record lines %s ; effective=%s, line %d"
        % (values["section_start"], values["section_end"], len(section),
           len(lines), census, values["record_lines"],
           "LAST" if latest_wins else "FIRST", eff_line))
    log("measured     = %s" % values["measured"])
    log("pin file     = %s" % values["pin"])
    log("lane entry   = %s" % effective)

    # ---- condition 3: entry-before-pin ordering ---------------------------
    # Both interruption directions of the re-pin protocol fail closed: a pin
    # rewrite without a landed entry, and a landed entry with a stale pin.
    # Requiring BOTH witnesses is that ordering, made terminal-state-checkable.
    pin_ok = values["measured"] == values["pin"]
    lane_ok = values["measured"] == effective
    if both_witnesses:
        disagree = []
        if not pin_ok:
            disagree.append("pin file witness (%s != measured %s)"
                            % (values["pin"], values["measured"]))
        if not lane_ok:
            disagree.append("lane entry witness line %d (%s != measured %s)"
                            % (eff_line, effective, values["measured"]))
        if disagree:
            detail = "; ".join(disagree)
            for d in disagree:
                log("REFUSE names: " + d)
            return ("REFUSE", detail, values)
        log("ACCEPT: measured == pin file == lane-recorded digest "
            "(both witnesses agree)")
        return ("ACCEPT", "both witnesses agree with the measured bytes",
                values)

    # MUTATION INSTRUMENT (order-blind): a single witness suffices. Exists
    # only so a mutation run can prove condition 3 load-bearing; never the
    # adopted behaviour.
    if pin_ok or lane_ok:
        detail = ("order-blind ACCEPT: measured matches %s alone"
                  % ("the pin file" if pin_ok
                     else "the lane entry line %d" % eff_line))
        log(detail)
        return ("ACCEPT", detail, values)
    detail = ("neither witness agrees with the measured bytes (pin %s, lane "
              "line %d %s, measured %s)"
              % (values["pin"], eff_line, effective, values["measured"]))
    log("REFUSE: " + detail)
    return ("REFUSE", detail, values)


def main(argv=None):
    import argparse
    p = argparse.ArgumentParser(
        description="Cross-witness pin check (qwen-coder/0220 reference "
                    "implementation). Exit 0 ACCEPT, 2 REFUSE, 3 NEITHER - an "
                    "exit code is not a result; the printed verdict is.")
    p.add_argument("--instrument", required=True)
    p.add_argument("--pin", required=True)
    p.add_argument("--lane", required=True)
    p.add_argument("--anchor", required=True)
    p.add_argument("--end-anchor", default=None)
    p.add_argument("--mutate-unanchored", action="store_true",
                   help="MUTATION MEASUREMENT ONLY: remove condition 1")
    p.add_argument("--mutate-anywhere-in-line", action="store_true",
                   help="MUTATION MEASUREMENT ONLY: remove condition 2")
    p.add_argument("--mutate-order-blind", action="store_true",
                   help="MUTATION MEASUREMENT ONLY: remove condition 3")
    p.add_argument("--mutate-first-wins", action="store_true",
                   help="MUTATION MEASUREMENT ONLY: remove condition 4")
    args = p.parse_args(argv)
    verdict, detail, _values = cross_witness_check(
        args.instrument, args.pin, args.lane, print, args.anchor,
        end_anchor=args.end_anchor,
        anchored=not args.mutate_unanchored,
        line_start=not args.mutate_anywhere_in_line,
        both_witnesses=not args.mutate_order_blind,
        latest_wins=not args.mutate_first_wins)
    print("VERDICT: %s" % verdict)
    print("DETAIL : %s" % detail)
    return {"ACCEPT": 0, "REFUSE": 2}.get(verdict, 3)


if globals().get("__name__") == "__main__":
    import sys
    sys.exit(main())
