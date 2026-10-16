#!/usr/bin/env python3
"""Mutation proof for the go/no-go page's guards. TASK 0230.

WHAT THIS ANSWERS. `src/gonogo.py` refuses in a dozen places and
`tests/test_go_is_impossible_while_a_row_is_unknown.py` is green. Neither
fact says a guard is WATCHED. This breaks one guard at a time and requires a
named test to die - and requires the DESIGNATED test to be among the dead,
not merely some bystander, because a test that reddens for any edit to a file
makes every mutation look killed.

THREE STATES, deliberately, because they are the three this page distinguishes
and conflating any pair of them is the defect it exists for:

    A   UNKNOWN   fail-closed reading: absent, unparseable, unrecognised,
                  disputed, poisoned - and the named rule, that GO is
                  impossible while any row is UNKNOWN
    B   STALE     age as a verdict: the threshold, the undated reading, the
                  future stamp, and STALE never reading as a pass
    C   GO        the reachability of GO, which is what stops every refusal
                  in state A being free, plus the two home-directory guards

HOW IT RUNS, AND WHY EACH STEP IS THERE.

The target is mutated as BYTES and the test module runs in a FRESH
SUBPROCESS, which reports failing test IDs programmatically rather than
having its text parsed - `unittest -v` wraps long names, and three of this
estate's findings are about a reader parsing a log wrong and calling the
result a measurement.

THE REVERT IS HASH-VERIFIED AND DOES NOT GO THROUGH GIT. In a lane worktree
no form of `git checkout` reverts correctly: the plain form changes bytes and
then reads clean, and `autocrlf=true` keeps the bytes and reads M. So the
original bytes are held in memory, written back, and the sha256 compared.

THE `.pyc` IS PURGED BEFORE EVERY RUN, and each run reports the sha256 of the
source it actually imported, taken from inside the subprocess. Python's
source-change check is whole-second, so a same-size mutation written inside a
second of the last one imports the PREVIOUS bytes and reads as a survivor;
`-B` only stops Python WRITING bytecode, it still reads what is there.

ONE SURVIVOR IS EXPECTED AND IS MARKED `SURVIVES`. See A1.
"""
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TARGET = os.path.join(ROOT, "src", "gonogo.py")
MODULE = "tests.test_go_is_impossible_while_a_row_is_unknown"

RUNNER = r'''
import hashlib, io, json, os, sys, unittest
sys.path.insert(0, os.path.abspath("."))
digest = hashlib.sha256(
    io.open(os.path.join("src", "gonogo.py"), "rb").read()).hexdigest()
loader = unittest.TestLoader()
suite = loader.loadTestsFromName(sys.argv[1])
result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)
print(json.dumps({
    "sha256": digest,
    "ran": result.testsRun,
    "failed": sorted(test.id() for test, _ in result.failures),
    "errored": sorted(test.id() for test, _ in result.errors),
    "load_errors": sorted(str(e) for e in getattr(loader, "errors", [])),
}))
'''

# (id, state, claim, [(old, new)], designated)
#
# `designated` is the test that exists FOR that guard, and every name in it
# must be among the dead. The full kill-set is reported as well and is often
# much larger - a mutation that breaks one of this page's own controls
# poisons every row to UNKNOWN by design, so thirty names go red and none of
# them proves anything on its own. The designated name is the claim; the rest
# is weather.
#
# An empty `designated` means the mutation is EXPECTED to survive, and the
# reason is written above it.
MUTATIONS = (
    # ------------------------------------------------- STATE A: UNKNOWN
    #
    # A1 IS A KNOWN SURVIVOR AND IS KEPT FOR THAT REASON. The comment in the
    # source used to claim the longest-first ORDER is what stops `NOT MET`
    # reading as a pass. It is not: `verdict_phrase` compares from the start
    # of the phrase, so `MET` never matches `NOT MET` at any ordering, and
    # swapping these two entries kills nothing. The claim was too strong and
    # has been corrected in the source. A1b is the mutation that observes the
    # guard which is actually load-bearing.
    ("A1", "UNKNOWN",
     "MET tried before NOT MET - a redundant second line of defence",
     [('    ("NOT MET", NOT_MET),\n'
       '    ("MET", MET),',
       '    ("MET", MET),\n'
       '    ("NOT MET", NOT_MET),')],
     []),

    ("A1b", "UNKNOWN",
     "the phrase is matched as a SUBSTRING, so MET-WITH-CAVEAT reads MET",
     [('        if upper == phrase or upper.startswith(phrase + " ") \\\n'
       '                or upper.startswith(phrase + ".") \\\n'
       '                or upper.startswith(phrase + ",") \\\n'
       '                or upper.startswith(phrase + "\\u2014") \\\n'
       '                or upper.startswith(phrase + " \\u2014"):',
       '        if phrase in upper:')],
     ["test_a_phrase_this_reader_does_not_know_is_unknown"]),

    ("A2", "UNKNOWN",
     "a phrase the reader does not know becomes MET",
     [("            return verdict, raw\n"
       "    return UNKNOWN, raw",
       "            return verdict, raw\n"
       "    return MET, raw")],
     ["test_a_phrase_this_reader_does_not_know_is_unknown"]),

    ("A3", "UNKNOWN",
     "a source that could not be read contributes no row at all",
     [('    for entry in chain:\n'
       '        if entry["state"] == PRESENT:\n'
       '            continue',
       '    for entry in chain:\n'
       '        if True:\n'
       '            continue')],
     ["test_an_absent_source_renders_its_question_unknown",
      "test_every_source_that_fails_still_produces_exactly_one_row",
      "test_an_unconfigured_estate_is_not_a_clear_board"]),

    ("A4", "UNKNOWN",
     "a present-but-unparseable source stays PRESENT",
     [('            if not parsed.get("rows"):',
       '            if False and not parsed.get("rows"):')],
     ["test_a_source_present_and_unparseable_renders_unknown_with_a_reason"]),

    ("A5", "UNKNOWN",
     "THE NAMED RULE: an UNKNOWN row no longer blocks GO",
     [("    if unknown:\n"
       "        # EVERY OTHER UNRESOLVED BUCKET",
       "    if False and unknown:\n"
       "        # EVERY OTHER UNRESOLVED BUCKET")],
     ["test_one_unknown_row_among_many_met_rows_is_not_go",
      "test_the_guard_is_the_one_that_fires",
      "test_no_arrangement_of_rows_with_an_unknown_can_be_go",
      "test_the_whole_render_cannot_say_go_with_an_unknown_row"]),

    ("A6", "UNKNOWN",
     "a failed control no longer poisons the rows",
     [('        if poison:\n'
       '            row["recorded"] = row["verdict"]',
       '        if False and poison:\n'
       '            row["recorded"] = row["verdict"]')],
     ["test_a_failed_control_is_reported_and_poisons_every_row"]),

    ("A7", "UNKNOWN",
     "the preflight's 23 NOT CLEARED becomes a clearance",
     [('    if counts["not_cleared"] > 0:\n'
       '        verdict = UNKNOWN',
       '    if counts["not_cleared"] > 0:\n'
       '        verdict = MET')],
     ["test_not_cleared_because_unknown_is_unknown_not_not_met"]),

    ("A8", "UNKNOWN",
     "two readings of one document that disagree take the table's",
     [('            row["verdict"] = UNKNOWN\n'
       '            row["disagreement"] = True',
       '            row["verdict"] = first["verdict"]\n'
       '            row["disagreement"] = True')],
     ["test_a_table_and_a_heading_that_disagree_render_unknown"]),

    # --------------------------------------------------- STATE B: STALE
    ("B1", "STALE",
     "a reading with no establishable time is called fresh",
     [('                "age_label": "no measurement time could be '
       'established",\n'
       '                "in_future": False, "stale": True}',
       '                "age_label": "no measurement time could be '
       'established",\n'
       '                "in_future": False, "stale": False}')],
     ["test_a_document_with_no_establishable_time_is_stale"]),

    ("B2", "STALE",
     "the threshold is widened a hundredfold",
     [('            "stale": age > STALE_SECONDS}',
       '            "stale": age > STALE_SECONDS * 100}')],
     ["test_a_reading_older_than_the_threshold_is_stale",
      "test_stale_is_a_different_word_from_not_met"]),

    ("B3", "STALE",
     "a stale row keeps its recorded verdict instead of going STALE",
     [('        if row["age"]["stale"] and row["verdict"] not in '
       '(UNKNOWN, WITHDRAWN):',
       '        if False and row["age"]["stale"]:')],
     ["test_a_reading_older_than_the_threshold_is_stale",
      "test_stale_is_a_different_word_from_not_met"]),

    ("B4", "STALE",
     "a STALE row no longer blocks GO",
     [('    if stale:\n'
       '        return NO_GO, (\n'
       '            "%d of %d rows are STALE',
       '    if False and stale:\n'
       '        return NO_GO, (\n'
       '            "%d of %d rows are STALE')],
     ["test_a_reading_older_than_the_threshold_is_stale"]),

    ("B5", "STALE",
     "the age is read from the newest timestamp anywhere in the file",
     [("    when = _stamp_with_time(head(text, lines))",
       "    when = _stamp_with_time(text)")],
     ["test_the_age_is_not_read_from_the_newest_timestamp_in_the_document"]),

    ("B6", "STALE",
     "a stamp in the future is called fresh",
     [('                "in_future": True, "stale": True}',
       '                "in_future": True, "stale": False}')],
     ["test_a_stamp_in_the_future_is_not_called_fresh"]),

    # ------------------------------------------------------ STATE C: GO
    ("C1", "GO",
     "the page is hard-wired to NO-GO",
     [('    return GO, (\n'
       '        "all %d rows read MET',
       '    return NO_GO, (\n'
       '        "all %d rows read MET')],
     ["test_a_fully_cleared_estate_renders_go",
      "test_every_control_passes"]),

    ("C2", "GO",
     "the control that proves GO is reachable cannot fail",
     [("    ok = verdict == GO and not not_met and bool(rows)",
       "    ok = True")],
     ["test_the_go_control_would_notice_a_page_wired_to_no_go"]),

    ("C3", "GO",
     "a cross-document dispute is resolved for the newer document",
     [('        row["verdict"] = UNKNOWN\n'
       '        row["reason"] = (\n'
       '            "%s - AND `%s` records the same question',
       '        row["verdict"] = WITHDRAWN\n'
       '        row["reason"] = (\n'
       '            "%s - AND `%s` records the same question')],
     ["test_a_question_another_document_voided_renders_unknown",
      "test_the_dispute_is_not_resolved_in_the_newer_document_s_favour"]),

    ("C4", "GO",
     "an empty TIER 2 is MET with no evidence the reader still works",
     [('        if out["items_seen"]:',
       '        if True:')],
     ["test_a_sheet_with_no_numbered_item_anywhere_is_unknown"]),

    ("C5", "GO",
     "a path with no estate anchor keeps its home directory",
     [('    return _HOME.sub("<home>", out)',
       '    return out')],
     ["test_no_home_directory_reaches_an_unread_source_s_path"]),

    ("C5b", "GO",
     "free prose keeps its home directory",
     [('    return _HOME.sub("<home>", text)',
       '    return text')],
     ["test_no_home_directory_reaches_the_page"]),

    ("C5c", "GO",
     "the estate-anchor cut is removed, so a published path keeps the "
     "segments above resonate-ops",
     [('        if index > 0 and _HOME.match(out[:index] or ""):\n'
       '            out = out[index:]',
       '        if False:\n'
       '            out = out[index:]')],
     ["test_the_redaction_keeps_the_anchor_and_drops_the_user"]),

    ("C6", "GO",
     "an item on the shortest list citing a MET row reads MET",
     [("        if verdict == MET:\n"
       "            # AN ITEM ON THE SHORTEST LIST",
       "        if False:\n"
       "            # AN ITEM ON THE SHORTEST LIST")],
     ["test_an_item_whose_precondition_reads_met_is_a_contradiction"]),

    ("C7", "GO",
     "a bare `P4` row with no verdict column goes unseen",
     [('        match = re.match(r"^ {2,}P(\\d{1,2})(?=[ \\t]|$)(.*)$", '
       'line.rstrip())',
       '        match = re.match(r"^ {2,}P(\\d{1,2})(?=[ \\t])(.*)$", '
       'line.rstrip())')],
     ["test_a_precondition_row_with_no_verdict_column_is_unknown"]),
)


def purge():
    for folder in ("src", "tests"):
        shutil.rmtree(os.path.join(ROOT, folder, "__pycache__"),
                      ignore_errors=True)


def run():
    purge()
    proc = subprocess.run([sys.executable, "-B", "-c", RUNNER, MODULE],
                          cwd=ROOT, capture_output=True)
    text = proc.stdout.decode("utf-8", "replace")
    for line in reversed(text.strip().splitlines()):
        if line.startswith("{"):
            return json.loads(line)
    raise SystemExit("no result from the runner:\n%s\n%s"
                     % (text[-2000:],
                        proc.stderr.decode("utf-8", "replace")[-2000:]))


def sha(path):
    return hashlib.sha256(io.open(path, "rb").read()).hexdigest()


def short(name):
    return name.split(".")[-1]


def main():
    original = io.open(TARGET, "rb").read()
    before = hashlib.sha256(original).hexdigest()
    print("target                             src/gonogo.py")
    print("sha256 before any mutation         %s" % before)
    print("CR bytes in the target             %d  (this worktree is LF)"
          % original.count(b"\r"))

    baseline = run()
    print("baseline   ran %d   failing %s"
          % (baseline["ran"],
             sorted(short(n) for n in
                    baseline["failed"] + baseline["errored"]) or "none"))
    if baseline["sha256"] != before:
        raise SystemExit("the subprocess read bytes this process did not "
                         "write: %s" % baseline["sha256"])
    pre_existing = set(baseline["failed"]) | set(baseline["errored"])

    results = []
    for ident, state, claim, edits, designated in MUTATIONS:
        counts = [original.count(old.encode("utf-8")) for old, _ in edits]
        if sorted(counts) != [1] * len(edits):
            print("%-4s NOT APPLIED - its site(s) appear %s times"
                  % (ident, counts))
            results.append({"id": ident, "state": state, "claim": claim,
                            "applied": False, "counts": counts,
                            "killed": [], "survived": None,
                            "designated": designated, "missing": designated})
            continue
        mutated_bytes = original
        for old, new in edits:
            mutated_bytes = mutated_bytes.replace(old.encode("utf-8"),
                                                  new.encode("utf-8"))
        io.open(TARGET, "wb").write(mutated_bytes)
        mutated_sha = sha(TARGET)
        if mutated_sha == before:
            raise SystemExit("%s changed nothing" % ident)
        got = run()
        io.open(TARGET, "wb").write(original)
        after = sha(TARGET)
        if after != before:
            raise SystemExit("REVERT FAILED after %s: %s" % (ident, after))
        killed = sorted((set(got["failed"]) | set(got["errored"]))
                        - pre_existing)
        shorts = {short(name) for name in killed}
        missing = [name for name in designated if name not in shorts]
        verdict = "LIVE" if not killed else "DEAD"
        if designated and missing:
            verdict = "WRONG"      # it died, and not for the stated reason
        if not designated and killed:
            verdict = "WRONG"      # it was expected to survive and did not
        results.append({"id": ident, "state": state, "claim": claim,
                        "applied": True, "killed": killed,
                        "designated": designated, "missing": missing,
                        "mutated_sha": mutated_sha,
                        "imported": got["sha256"], "ran": got["ran"],
                        "load_errors": got["load_errors"],
                        "survived": not killed, "verdict": verdict})
        print("%-4s %-7s %-5s %2d killed  imported %s  %s"
              % (ident, state, verdict, len(killed), got["sha256"][:12],
                 claim))
        for name in designated:
            print("       %-5s designated  %s"
                  % ("DEAD" if name in shorts else "ALIVE", name))
        others = sorted(shorts - set(designated))
        if others:
            print("       %d other name(s) also red: %s"
                  % (len(others), ", ".join(others[:4])
                     + (" ..." if len(others) > 4 else "")))

    final = sha(TARGET)
    print("\nsha256 after every revert          %s" % final)
    print("identical to the start             %s" % (final == before))
    wrong = [r["id"] for r in results if r.get("verdict") == "WRONG"]
    live = [r["id"] for r in results if r.get("survived")]
    print("mutations %d   dead %d   expected survivors %s   WRONG %s"
          % (len(results),
             len([r for r in results if r.get("verdict") == "DEAD"]),
             [r["id"] for r in results
              if r.get("survived") and not r["designated"]] or "none",
             wrong or "none"))
    # The result goes to `work/`, which is gitignored: it is a measurement of
    # one run on one machine, and a harness writing its own output into the
    # tree charges a stray file to whatever change is measured next.
    out = os.path.join(ROOT, "work", "gonogo-mutations.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    io.open(out, "w", encoding="utf-8").write(json.dumps(
        {"before": before, "after": final, "baseline_ran": baseline["ran"],
         "pre_existing": sorted(pre_existing), "results": results}, indent=1))
    purge()
    return 1 if wrong or final != before else 0


if __name__ == "__main__":                                  # pragma: no cover
    sys.exit(main())
