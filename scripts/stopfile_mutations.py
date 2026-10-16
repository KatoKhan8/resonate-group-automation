#!/usr/bin/env python3
"""Mutation proof for the STOP-file verdicts. TASK-0260.

WHAT THIS ANSWERS. `tests/test_a_lane_down_on_purpose_is_not_a_lane_to_restart`
is green and 39 tests passed the first time they ran. Neither fact says a
guard is WATCHED - and the guard that matters here is a NEGATIVE one: that a
lane whose STOP file cannot be read never renders STOPPED. A fail-closed
default is the easiest thing in this estate to leave unobserved, because the
state it protects against is the state nobody creates by accident.

So each guard is broken one at a time and a NAMED test has to die for it. The
designated name is the claim; everything else that reddens is weather. A test
that goes red for any edit to a file makes every mutation look killed, which
is why `missing` - a designated name still ALIVE under its own mutation -
reports WRONG rather than DEAD.

THREE TARGETS, because the answer is assembled across three modules and a
harness that mutated only the reader would prove nothing about the two pages
that render it:

    src/lanes.py        the reading, the date rule, and the verdict
    src/web/pages.py    the cell a person reads, and its colour
    src/queuedepth.py   the OTHER page, the one whose words say "restart"

HOW IT RUNS, AND WHY EACH STEP IS THERE. Lifted from
`scripts/gonogo_mutations.py` deliberately, because these steps are each a
finding this estate already paid for:

  * the target is mutated as BYTES and reverted from bytes held in memory,
    hash-verified, never through git - in a lane worktree no form of
    `git checkout` reverts correctly;
  * the test module runs in a FRESH SUBPROCESS which reports failing test IDs
    as JSON, rather than having `unittest -v` output parsed - that wraps long
    names and three of this estate's findings are a reader parsing a log
    wrong and calling the result a measurement;
  * the `.pyc` is purged before every run and each run prints the sha256 of
    the source it actually imported, taken from INSIDE the subprocess.
    Python's source-change check is whole-second, so a same-size mutation
    written inside a second of the last one imports the PREVIOUS bytes and
    reads as a survivor.

Nothing here touches `resonate-ops`. The test module it runs builds its own
estate in a temporary directory, and no STOP file outside that directory is
opened, created or removed by any part of this.
"""
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODULE = "tests.test_a_lane_down_on_purpose_is_not_a_lane_to_restart"

#: Every file a mutation may touch, and every file whose sha256 the runner
#: reports back. A mutation that landed in a file this list does not name
#: would be invisible to the revert check.
TARGETS = ("src/lanes.py", "src/web/pages.py", "src/queuedepth.py")

RUNNER = r'''
import hashlib, io, json, os, sys, unittest
sys.path.insert(0, os.path.abspath("."))
targets = sys.argv[2].split(",")
digests = {}
for rel in targets:
    digests[rel] = hashlib.sha256(
        io.open(os.path.join(*rel.split("/")), "rb").read()).hexdigest()
loader = unittest.TestLoader()
suite = loader.loadTestsFromName(sys.argv[1])
result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)
print(json.dumps({
    "sha256": digests,
    "ran": result.testsRun,
    "failed": sorted(test.id() for test, _ in result.failures),
    "errored": sorted(test.id() for test, _ in result.errors),
    "load_errors": sorted(str(e) for e in getattr(loader, "errors", [])),
}))
'''

# (id, target, claim, [(old, new)], designated)
#
# An empty `designated` means the mutation is EXPECTED to survive, and the
# reason is written above it.
MUTATIONS = (
    # ------------------------------------- THE FAIL-CLOSED DEFAULT ITSELF
    #
    # The whole point of the task. Each of these makes an unestablished
    # state render as the operator's deliberate decision, which is the
    # substitution this estate has paid for twice.
    ("F1", "src/lanes.py",
     "no STOP file at all renders STOPPED",
     [('    if stop["state"] != PRESENT:\n'
       '        return V_DOWN_UNEXPLAINED',
       '    if stop["state"] != PRESENT:\n'
       '        return V_STOPPED')],
     ["test_C1_down_unexplained_fires",
      "test_the_unexplained_cell_does_not_offer_a_lift_date",
      "test_an_unexplained_lane_is_still_stranded",
      "test_an_empty_stop_file_is_not_stopped",
      "test_an_unreadable_stop_file_is_not_stopped"]),

    ("F2", "src/lanes.py",
     "a STOP file with NO READABLE DATE renders STOPPED",
     [('    if stop["expired"] is False:\n'
       '        return V_STOPPED\n'
       '    return V_DOWN_UNEXPLAINED',
       '    if stop["expired"] is False:\n'
       '        return V_STOPPED\n'
       '    return V_STOPPED')],
     ["test_a_stop_file_with_no_date_is_not_stopped"]),

    ("F3", "src/lanes.py",
     "the whole refinement is dropped and every down lane is V_DOWN again",
     [("        verdict = down_verdict(stop)",
       "        verdict = V_DOWN")],
     ["test_C1_down_unexplained_fires", "test_C2_stopped_fires",
      "test_C3_stop_expired_fires",
      "test_the_old_down_verdict_is_no_longer_produced"]),

    ("F4", "src/lanes.py",
     "a STOP file is read as evidence that the WATCHER is down",
     [("    if status == UNKNOWN:\n"
       "        verdict = V_UNKNOWN",
       "    if stop[\"state\"] == PRESENT:\n"
       "        verdict = down_verdict(stop)\n"
       "    elif status == UNKNOWN:\n"
       "        verdict = V_UNKNOWN")],
     ["test_an_unreadable_log_stays_unknown_beside_a_stop_file",
      "test_an_unreadable_process_table_does_not_produce_stopped",
      "test_a_live_lane_with_a_stop_file_keeps_its_verdict_and_is_flagged"]),

    # ------------------------------------------------------ THE DATE RULE
    ("D1", "src/lanes.py",
     "the date is HARD-CODED, which is what the brief forbids by name",
     [('    row["lift_state"] = LIFT_READ\n'
       '    row["lift_when"] = when\n'
       '    row["lift_at"] = shown',
       '    row["lift_state"] = LIFT_READ\n'
       '    when = datetime.datetime(2026, 10, 21, 21, 0)\n'
       '    row["lift_when"] = when\n'
       '    row["lift_at"] = "2026-10-21 21:00"')],
     ["test_a_different_date_is_read_as_itself",
      "test_C3_stop_expired_fires"]),

    ("D2", "src/lanes.py",
     "the EARLIEST date is taken, which expires this stop five days early",
     [("    when, shown, line = max(found, key=lambda item: item[0])",
       "    when, shown, line = min(found, key=lambda item: item[0])")],
     ["test_the_latest_of_several_dates_is_used",
      "test_the_first_date_is_not_used"]),

    ("D3", "src/lanes.py",
     "a bare date is read as MIDNIGHT, expiring the stop a day early",
     [("                    when = datetime.datetime(int(year), int(month), "
       "int(day),\n                                             23, 59, 59)",
       "                    when = datetime.datetime(int(year), int(month), "
       "int(day),\n                                             0, 0, 0)")],
     ["test_a_bare_date_is_the_end_of_that_day"]),

    ("D4", "src/lanes.py",
     "a string shaped like a date and not one is CLAMPED into a lift moment",
     [("            except ValueError:\n"
       "                # `2026-13-45` matches the shape and is not a date. "
       "Skipped\n"
       "                # rather than clamped into the nearest plausible "
       "day.\n"
       "                continue",
       "            except ValueError:\n"
       "                when = datetime.datetime(2099, 1, 1)\n"
       "                shown = \"%s-%s-%s\" % (year, month, day)")],
     ["test_a_string_shaped_like_a_date_and_is_not_one_is_skipped"]),

    ("D5", "src/lanes.py",
     "the reader needs an ENGLISH label, so the operator's own file is unread",
     [('_STOP_DATETIME = re.compile(r"(\\d{4})-(\\d{2})-(\\d{2})'
       '(?:[ T](\\d{1,2}):(\\d{2}))?")',
       '_STOP_DATETIME = re.compile(r"until (\\d{4})-(\\d{2})-(\\d{2})'
       '(?:[ T](\\d{1,2}):(\\d{2}))?")')],
     ["test_C2_stopped_fires", "test_the_latest_of_several_dates_is_used",
      "test_a_stopped_lane_is_not_stranded"]),

    # ------------------------------------------------ IS IT READING THE DISK
    ("C4", "src/lanes.py",
     "the first reading is cached forever, which passes C1-C3 and is blind",
     [("def stop_reading(root, lane, now=None, name=None):",
       "_STOP_CACHE = {}\n\n\n"
       "def stop_reading(root, lane, now=None, name=None):\n"
       "    key = (root, lane, name)\n"
       "    if key not in _STOP_CACHE:\n"
       "        _STOP_CACHE[key] = _stop_reading(root, lane, now, name)\n"
       "    return _STOP_CACHE[key]\n\n\n"
       "def _stop_reading(root, lane, now=None, name=None):")],
     ["test_the_same_lane_flips_back_in_one_process_run",
      "test_an_edited_date_is_seen_without_a_restart"]),

    # ------------------------------------------------------ THE CONTRADICTION
    ("X1", "src/lanes.py",
     "a STOP file on a lane that is ALIVE is never flagged",
     [('        "stop_contradicted": bool(stop["state"] == PRESENT\n'
       '                                  and verdict in LIVE_VERDICTS),',
       '        "stop_contradicted": bool(stop["state"] == PRESENT\n'
       '                                  and verdict in ()),')],
     ["test_a_live_lane_with_a_stop_file_keeps_its_verdict_and_is_flagged"]),

    ("X2", "src/lanes.py",
     "it fires on every down lane too, which cries wolf on all three",
     [("LIVE_VERDICTS = (V_RUNNING, V_ORPHANED, V_STUCK)",
       "LIVE_VERDICTS = (V_RUNNING, V_ORPHANED, V_STUCK, V_STOPPED)")],
     ["test_a_down_lane_is_not_flagged_as_a_contradiction"]),

    # --------------------------------------------------- THE TERMINAL RENDER
    ("T1", "src/lanes.py",
     "the label is truncated to its first word, so UNEXPLAINED reads DOWN",
     [('            % (row["lane"], VERDICT_TEXT[row["verdict"]][0],',
       '            % (row["lane"], VERDICT_TEXT[row["verdict"]][0]'
       '.split()[0],')],
     ["test_the_whole_label_is_printed"]),

    ("T2", "src/lanes.py",
     "the stopped line loses the date and the depth",
     [('        if row["verdict"] == V_STOPPED:\n'
       '            out.append("      DOWN ON PURPOSE until %s. %s brief(s) '
       'wait "',
       '        if False and row["verdict"] == V_STOPPED:\n'
       '            out.append("      DOWN ON PURPOSE until %s. %s brief(s) '
       'wait "')],
     ["test_the_stopped_line_carries_the_date_and_the_depth"]),

    # ----------------------------------------------- THE CELL A PERSON READS
    ("P1", "src/web/pages.py",
     "STOPPED is drawn in ALARM RED, so a decision reads as a fault",
     [('    "stopped": "",\n    "stop_expired": "warn",',
       '    "stopped": "block",\n    "stop_expired": "warn",')],
     ["test_every_new_verdict_has_words_and_a_colour"]),

    ("P2", "src/web/pages.py",
     "the block is computed and never rendered - existence is not function",
     [("            + _stop_block(row)",
       "            + \"\"")],
     ["test_the_date_it_lifts_is_in_the_cell",
      "test_the_queued_work_is_named_as_intact",
      "test_restarting_early_is_named_as_a_cost",
      "test_the_operators_own_first_line_is_quoted"]),

    ("P3", "src/web/pages.py",
     "an UNKNOWN queue is rendered as intact work",
     [('    if row["queue_depth"] is None:\n'
       '        out += (\'<div class="small">\'\n'
       '                + tag("queued work UNKNOWN", "block")',
       '    if False:\n'
       '        out += (\'<div class="small">\'\n'
       '                + tag("queued work UNKNOWN", "block")')],
     ["test_an_unknown_queue_is_not_rendered_as_intact"]),

    ("P4", "src/web/pages.py",
     "the STOP file's path goes into a `<code>` chip he can paste as a command",
     [('        out += (\'<div class="small muted">\'\n'
       '                + esc("the file is " + stop["path_shown"]',
       '        out += (\'<div class="small muted"><code>\'\n'
       '                + esc("the file is " + stop["path_shown"]')],
     ["test_the_file_is_named_without_a_code_chip"]),

    ("P5", "src/web/pages.py",
     "the depth panel drops the STOPPED note and only the red one is left",
     [('    if data["stopped_lanes"]:\n'
       '        notes += (\'<p class="note">\' + tag("STOPPED ON PURPOSE", "")',
       '    if False and data["stopped_lanes"]:\n'
       '        notes += (\'<p class="note">\' + tag("STOPPED ON PURPOSE", "")')],
     ["test_the_restart_sentence_is_not_printed_for_it"]),

    # -------------------------------------------------- THE OTHER PAGE'S WORDS
    ("Q1", "src/queuedepth.py",
     "a stopped lane is STRANDED again - 'the repair is restarting the watcher'",
     [("    elif watcher == W_DEAD and stopped:",
       "    elif False and stopped:")],
     ["test_a_stopped_lane_is_not_stranded",
      "test_the_restart_sentence_is_not_printed_for_it",
      "test_a_stopped_lane_with_nothing_queued_is_still_stopped",
      "test_the_briefs_are_counted_and_not_lost_to_the_split"]),

    ("Q2", "src/queuedepth.py",
     "the stranded total counts the stopped lanes its own sentence omits",
     [('    out["stranded_briefs"] = sum(r["raw_depth"] or 0 for r in rows\n'
       '                                 if r["state"] == S_STRANDED)',
       '    out["stranded_briefs"] = sum(r["raw_depth"] or 0 for r in rows\n'
       '                                 if r["watcher"] == W_DEAD)')],
     ["test_the_briefs_are_counted_and_not_lost_to_the_split"]),

    ("Q3", "src/queuedepth.py",
     "the terminal render stops naming the stopped briefs at all",
     [('    if data["stopped_lanes"]:\n'
       '        # SAID EVEN THOUGH THE LINE ABOVE NO LONGER COUNTS THESE.',
       '    if False and data["stopped_lanes"]:\n'
       '        # SAID EVEN THOUGH THE LINE ABOVE NO LONGER COUNTS THESE.')],
     ["test_the_briefs_are_counted_and_not_lost_to_the_split"]),

    ("Q4", "src/queuedepth.py",
     "a stopped lane with no briefs falls through to DEAD AND EMPTY",
     [("    elif watcher == W_DEAD and stopped:\n"
       "        # BEFORE THE STRANDED TEST",
       "    elif watcher == W_DEAD and stopped and (raw or 0) > 0:\n"
       "        # BEFORE THE STRANDED TEST")],
     ["test_a_stopped_lane_with_nothing_queued_is_still_stopped"]),
)


def purge():
    for folder in ("src", os.path.join("src", "web"), "tests"):
        shutil.rmtree(os.path.join(ROOT, folder, "__pycache__"),
                      ignore_errors=True)


def run():
    purge()
    proc = subprocess.run([sys.executable, "-B", "-c", RUNNER, MODULE,
                           ",".join(TARGETS)],
                          cwd=ROOT, capture_output=True)
    text = proc.stdout.decode("utf-8", "replace")
    for line in reversed(text.strip().splitlines()):
        if line.startswith("{"):
            return json.loads(line)
    raise SystemExit("no result from the runner:\n%s\n%s"
                     % (text[-2000:],
                        proc.stderr.decode("utf-8", "replace")[-2000:]))


def path_of(rel):
    return os.path.join(ROOT, *rel.split("/"))


def sha(path):
    return hashlib.sha256(io.open(path, "rb").read()).hexdigest()


def short(name):
    return name.split(".")[-1]


def main():
    original = {rel: io.open(path_of(rel), "rb").read() for rel in TARGETS}
    before = {rel: hashlib.sha256(blob).hexdigest()
              for rel, blob in original.items()}
    for rel in TARGETS:
        print("%-20s sha256 %s   CR=%d"
              % (rel, before[rel][:16], original[rel].count(b"\r")))
    print("(this worktree is LF, so CR=0 on every target)")

    baseline = run()
    print("\nbaseline   ran %d   failing %s"
          % (baseline["ran"],
             sorted(short(n) for n in
                    baseline["failed"] + baseline["errored"]) or "none"))
    if baseline["sha256"] != before:
        raise SystemExit("the subprocess read bytes this process did not "
                         "write: %s" % baseline["sha256"])
    pre_existing = set(baseline["failed"]) | set(baseline["errored"])

    results = []
    for ident, rel, claim, edits, designated in MUTATIONS:
        blob = original[rel]
        counts = [blob.count(old.encode("utf-8")) for old, _ in edits]
        if sorted(counts) != [1] * len(edits):
            print("%-4s NOT APPLIED - its site(s) appear %s times in %s"
                  % (ident, counts, rel))
            results.append({"id": ident, "target": rel, "claim": claim,
                            "applied": False, "counts": counts,
                            "killed": [], "survived": None,
                            "verdict": "NOT APPLIED",
                            "designated": designated,
                            "missing": designated})
            continue
        mutated = blob
        for old, new in edits:
            mutated = mutated.replace(old.encode("utf-8"),
                                      new.encode("utf-8"))
        io.open(path_of(rel), "wb").write(mutated)
        mutated_sha = sha(path_of(rel))
        if mutated_sha == before[rel]:
            raise SystemExit("%s changed nothing" % ident)
        got = run()
        io.open(path_of(rel), "wb").write(blob)
        after = sha(path_of(rel))
        if after != before[rel]:
            raise SystemExit("REVERT FAILED after %s: %s" % (ident, after))
        # THE LOAD PROOF. The subprocess reports the sha256 it read, so a
        # same-second same-size mutation that imported stale bytecode is
        # visible here instead of reading as a survivor.
        if got["sha256"].get(rel) != mutated_sha:
            raise SystemExit("%s: the runner imported %s, not the mutant %s"
                             % (ident, got["sha256"].get(rel), mutated_sha))
        killed = sorted((set(got["failed"]) | set(got["errored"]))
                        - pre_existing)
        shorts = {short(name) for name in killed}
        missing = [name for name in designated if name not in shorts]
        verdict = "LIVE" if not killed else "DEAD"
        if designated and missing:
            verdict = "WRONG"      # it died, and not for the stated reason
        if not designated and killed:
            verdict = "WRONG"      # it was expected to survive and did not
        results.append({"id": ident, "target": rel, "claim": claim,
                        "applied": True, "killed": killed,
                        "designated": designated, "missing": missing,
                        "mutated_sha": mutated_sha,
                        "imported": got["sha256"].get(rel), "ran": got["ran"],
                        "load_errors": got["load_errors"],
                        "survived": not killed, "verdict": verdict})
        print("%-4s %-18s %-5s %2d killed  imported %s  %s"
              % (ident, rel.split("/")[-1], verdict, len(killed),
                 mutated_sha[:12], claim))
        for name in designated:
            print("       %-5s designated  %s"
                  % ("DEAD" if name in shorts else "ALIVE", name))
        others = sorted(shorts - set(designated))
        if others:
            print("       %d other name(s) also red: %s"
                  % (len(others), ", ".join(others[:4])
                     + (" ..." if len(others) > 4 else "")))

    final = {rel: sha(path_of(rel)) for rel in TARGETS}
    print("\nsha256 after every revert, identical to the start: %s"
          % (final == before))
    for rel in TARGETS:
        print("  %-20s %s  %s" % (rel, final[rel][:16],
                                  "same" if final[rel] == before[rel]
                                  else "DIFFERENT"))
    wrong = [r["id"] for r in results if r.get("verdict") in ("WRONG",
                                                              "NOT APPLIED")]
    print("mutations %d   dead %d   survivors %s   WRONG/NOT APPLIED %s"
          % (len(results),
             len([r for r in results if r.get("verdict") == "DEAD"]),
             [r["id"] for r in results if r.get("survived")] or "none",
             wrong or "none"))
    out = os.path.join(ROOT, "work", "stopfile-mutations.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    io.open(out, "w", encoding="utf-8").write(json.dumps(
        {"before": before, "after": final, "baseline_ran": baseline["ran"],
         "pre_existing": sorted(pre_existing), "results": results}, indent=1))
    purge()
    return 1 if wrong or final != before else 0


if __name__ == "__main__":                                  # pragma: no cover
    sys.exit(main())
