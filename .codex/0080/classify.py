# TASK-0080 -- Layer 2: TASK-0075's clearing rule as a pure function over the
# facts Layer 1 extracted.  Verdicts are SAFE / UNKNOWN / AFFECTED, fail
# closed: a record missing a clearing fact is UNKNOWN, never SAFE, and a
# demonstrated stale import is AFFECTED no matter what else the record says.
#
# THE RULE (0075, restated):
#   SAFE      (any one of)
#     a. named-reason kill -- a named test died with a stated signature.  A
#        red run cannot be forged by stale bytecode (stale bytecode can only
#        counterfeit a GREEN verdict -- 0078 section 3), and the named
#        signature is what makes the red the mutant's own.
#     b. the mutation changed the file's byte length -- stated in the record,
#        or arithmetic on two verbatim-quoted strings -- so the pyc header's
#        size field could not match and a recompile was forced.
#     c. a recorded whole-second difference that invalidated the header (the
#        plant's mtime in a different whole second than the primed pyc's, or
#        a revert in a strictly later whole second).
#     d. a recorded pyc precaution -- the entry deleted __pycache__ between
#        plant and run (qwen/0176's "no pyc existed when the mutant was
#        imported", in its recorded form).
#     e. not an in-place mutation at all (cross-tree differential,
#        fixture-level simulation): no module was overwritten, so no reload
#        event exists to be stale.
#   AFFECTED  the record itself demonstrates the verdict came from stale
#             bytes (stale-bytecode proof, "behaved as the ORIGINAL",
#             would-reuse header over planted disk).
#   UNKNOWN   everything else, including every survivor with no clearing
#             fact and every kill whose reason is described but not named.
#             Fail-closed: size not recorded means SAFE cannot be printed.
def classify_facts(r):
    """r is a Layer-1 record dict (or a synthetic dict of the same shape, as
    the C2 replay feeds it).  Returns (verdict, cleared_by, missing)."""
    missing = []

    # 1. A demonstrated stale import voids the verdict, whatever else holds.
    if r.get("stale_marker"):
        return "AFFECTED", "stale-proof recorded: %s" % r["stale_marker"], []

    # 2. No in-place module write -> no reload event -> nothing to be stale.
    if r.get("entry_not_in_place"):
        return "SAFE", "cross-tree/fixture record: no in-place module write", []

    named_kill = (r.get("outcome") == "kill" and r.get("names")
                  and r.get("signature"))
    if named_kill:
        return "SAFE", ("named-reason kill (%s died with stated signature "
                        "'%s'; a red cannot be forged by stale bytecode)"
                        % (r["names"][0], r["signature"])), []

    if r.get("loadproof_clear"):
        return "SAFE", ("recorded load-proof CLEAN -- module object proven "
                        "equal to disk bytes at verdict time (0078's "
                        "instrument; subsumes the pyc-precaution test)"), []

    size_change = (r.get("size_change") in ("change-claim", "change-derived")
                   or r.get("entry_size_change"))
    if size_change:
        how = ("recorded size claim" if
               (r.get("size_change") == "change-claim"
                or r.get("entry_size_change")) else
               "derived from verbatim pair (delta %+d B)"
               % r.get("derived_delta", 0))
        return "SAFE", "byte length changed -> recompile forced (%s)" % how, []

    if r.get("second_clearing"):
        return "SAFE", "whole-second difference recorded -> header invalidated", []

    if r.get("pyc_precaution_local") or r.get("entry_pyc_precaution"):
        return "SAFE", "recorded __pycache__ deletion between plant and run", []

    # fail closed
    if r.get("outcome") == "kill":
        if not r.get("names"):
            missing.append("no clause-local test name")
        if not r.get("signature"):
            missing.append("no stated signature")
    elif r.get("outcome") == "survive":
        missing.append("survivor verdict")
    else:
        missing.append("stale-only record with no clearing fact")
    missing.append("no recorded size change / second difference / pyc precaution")
    return "UNKNOWN", "; ".join(missing), missing


def classify_records(records):
    out = []
    for r in records:
        verdict, reason, missing = classify_facts(r)
        rr = dict(r)
        rr["verdict"], rr["reason"] = verdict, reason
        out.append(rr)
    return out


def tally(classified):
    counts = {"SAFE": 0, "UNKNOWN": 0, "AFFECTED": 0}
    for r in classified:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    return counts
