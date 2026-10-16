"""Mutate `src.queuedepth` one edit at a time and name the kill-set each way.

WHY THE REVERT IS A BYTE BACKUP AND NOT `git checkout --`. This repository's
shared config sets `core.autocrlf=true` and clearing `GIT_CONFIG_SYSTEM` does
not turn it off, so a checkout in an LF tree rewrites every line ending while
`git status` goes on calling the file clean. The bytes would differ from the
bytes the measurement was taken against and nothing would say so. The pristine
file is copied to a temporary path first, every revert is a byte copy back, and
every revert is verified by md5 - the one check an index stat cannot fool.

WHY EACH MUTATION IS RUN ALONE AND PREDICTED FIRST. A mutation whose kill-set
is merely non-empty proves nothing: a test that reddens for ANY edit to the
mutated file makes every mutation look killed. So each declares the tests it
SHOULD kill, and three sets are reported - predicted-and-killed,
predicted-and-SURVIVED, and killed-but-not-predicted. The second is a missing
test. The third is collateral and is printed rather than counted as a win.

THE PAIR IS THE MEASUREMENT. `0130` recorded that one of its controls could
not detect a classifier answering the same every time, and `0160` repeated the
finding. So `M5` makes consumable depth always 0 and `M6` makes it always the
raw depth, and the kill-sets are named each way: the first must redden `C1`
alone of the three, the second must redden `C2` and `C3`.

    py -3 scripts/depth_mutations.py
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(ROOT, "src", "queuedepth.py")
MODULE = "tests.test_the_depth_that_cannot_be_consumed"

#: `(name, what it breaks, [(before, after), ...], [predicted kills])`.
#: Every `before` must occur EXACTLY ONCE in the file; the harness refuses
#: the mutation otherwise, because a replace that hit two sites is two
#: mutations and the kill-set would not say which one was observed.
MUTATIONS = (
    ("M1",
     "C2's mutation: the watcher-liveness read always answers ALIVE",
     [('    if row.get("watcher_went_down"):\n'
       '        return W_DEAD, ("this lane\'s own log records `watcher '
       'down.` - the "\n'
       '                        "watcher reported its own exit")',
       '    if True:\n'
       '        return W_LIVE, ("this lane\'s own log records `watcher '
       'down.` - the "\n'
       '                        "watcher reported its own exit")')],
     ["test_the_consumable_depth_is_zero",
      "test_the_watcher_reads_dead_from_the_pid_table",
      "test_below_floor_is_re_derived_from_the_dead_watchers_zero",
      "test_the_raw_verdict_said_it_was_compliant",
      "test_the_state_is_stranded_and_not_starved",
      "test_the_estate_counts_the_stranded_briefs",
      "test_a_watcher_that_logged_its_own_exit_is_dead_too",
      "test_a_dead_watcher_with_an_empty_queue_is_not_stranded"]),

    ("M2",
     "C3's mutation: the already-landed subtraction is removed",
     [('        landed_names = {item["brief"] for item in '
       'landing["landed"]}',
       '        landed_names = set()')],
     ["test_the_consumable_depth_is_one",
      "test_below_floor_is_re_derived_from_the_one_brief_left",
      "test_the_two_depths_and_the_subtraction_are_consistent",
      "test_the_id_is_compared_for_equality_and_not_containment",
      "test_pilotcaps_sat_at_the_floor_with_nothing_to_do",
      "test_pilotcaps_is_starved_and_not_stranded"]),

    ("M3",
     "C4's mutation: the brief locked in RUNNING\\ is counted as queued",
     [('    raw = row.get("queue_depth")',
       '    raw = ((row.get("queue_depth") or 0)\n'
       '           + len(row.get("inflight") or []))')],
     ["test_it_is_not_counted_as_queued",
      "test_qwens_locked_brief_is_named_and_counted_nowhere_else",
      "test_the_sixteen_stranded_briefs_are_counted",
      "test_the_estate_totals_name_both_numbers",
      "test_an_unreadable_queue_folder_is_unknown_in_both_depths"]),

    ("M4",
     "C5's mutation: an unreadable lane file falls back to the raw depth",
     [('    if state in (lanes.ABSENT, lanes.UNREADABLE):\n'
       '        return out',
       '    if False:\n'
       '        return out')],
     ["test_the_landed_count_is_unknown_and_not_zero",
      "test_the_consumable_depth_is_unknown",
      "test_it_does_not_fall_back_on_the_raw_depth",
      "test_below_floor_is_unknown_too",
      "test_the_reason_is_named_with_its_repair",
      "test_the_state_is_unknown_and_not_ok",
      "test_an_absent_lane_file_is_unknown_as_well",
      "test_an_unknown_lane_is_in_neither_total",
      "test_an_unknown_renders_as_unknown_and_never_as_zero",
      "test_the_unknown_names_the_authority_that_was_missing",
      "test_the_denominator_is_printed_with_every_total"]),

    ("M5",
     "C6, direction one: the consumable calculation always returns 0",
     [('        consumable = len([n for n in queued if n not in '
       'landed_names])',
       '        consumable = 0')],
     ["test_the_consumable_depth_equals_the_raw_depth",
      "test_it_is_not_below_the_floor_on_either_number",
      "test_the_state_is_ok_and_not_starved",
      "test_the_estate_totals_cover_every_lane",
      "test_the_consumable_depth_is_one",
      "test_the_two_depths_and_the_subtraction_are_consistent",
      "test_the_id_is_compared_for_equality_and_not_containment",
      "test_an_empty_lane_file_is_an_answer_and_lands_nothing"]),

    ("M6",
     "C6, direction two: the consumable depth always equals the raw depth",
     [("    if watcher == W_DEAD:\n"
       "        # THE ONE SHORT CIRCUIT",
       "    if False:\n"
       "        # THE ONE SHORT CIRCUIT"),
      ("    elif why:\n        consumable = None",
       "    elif False:\n        consumable = None"),
      ('        landed_names = {item["brief"] for item in '
       'landing["landed"]}',
       '        landed_names = set()')],
     # THREE PREDICTIONS WERE WRONG HERE ON THE FIRST RUN AND THE TESTS
     # WERE RIGHT TO SURVIVE: `test_the_estate_counts_the_stranded_briefs`,
     # `test_the_state_is_stranded_and_not_starved` and
     # `test_zero_is_a_measurement_and_not_an_unknown` all rest on the
     # WATCHER reading, which this mutation does not touch - it bypasses
     # the consumable short-circuit, not the liveness that produced it. A
     # dead watcher is still dead, so a stranded lane is still stranded and
     # its depth is still a measurement. The prediction was wrong rather
     # than the coverage, and the C2 assertions that DO rest on the number
     # are all in the list.
     ["test_the_consumable_depth_is_zero",
      "test_below_floor_is_re_derived_from_the_dead_watchers_zero",
      "test_below_floor_is_re_derived_from_the_one_brief_left",
      "test_the_raw_verdict_said_it_was_compliant",
      "test_a_watcher_that_logged_its_own_exit_is_dead_too",
      "test_the_consumable_depth_is_one",
      "test_the_two_depths_and_the_subtraction_are_consistent",
      "test_the_id_is_compared_for_equality_and_not_containment",
      "test_the_consumable_depth_is_unknown",
      "test_it_does_not_fall_back_on_the_raw_depth"]),

    ("M7",
     "starvation and stranding become one state, which is the family-6 "
     "failure this panel exists to stop",
     [("        state = S_STRANDED if (raw or 0) > 0 or locked "
       "else S_DEAD_EMPTY",
       "        state = S_STARVED")],
     ["test_and_they_are_different_states",
      "test_the_estate_lists_them_separately",
      "test_the_state_is_stranded_and_not_starved",
      "test_a_dead_watcher_with_an_empty_queue_is_not_stranded",
      "test_not_one_of_the_four_renders_as_healthy",
      "test_pilotcaps_is_starved_and_not_stranded"]),

    ("M8",
     "`below_floor` falls back to the RAW verdict when the consumable "
     "depth is UNKNOWN - the fail-closed rule `0110` set",
     [("    below = (None if consumable is None or floor is None\n"
       "             else consumable < floor)",
       "    below = (below_raw if consumable is None or floor is None\n"
       "             else consumable < floor)")],
     # ONE PREDICTION WAS WRONG AND ONE FOUND A REAL GAP.
     # `test_an_unreadable_queue_folder_is_unknown_in_both_depths` survives
     # correctly: there the RAW verdict is None too, so the fallback has
     # nothing to fall back on and changes no value.
     # `test_an_unknown_renders_as_unknown_and_never_as_zero` survived
     # because it asserts that UNKNOWN appears at all, and the consumable
     # cell still says it - so the render consequence of this mutation, a
     # row whose floor cell prints a clean verdict beside a consumable cell
     # that says UNKNOWN, was observed by nothing.
     # `test_the_consumable_floor_cell_is_unknown_and_never_a_no` was
     # written for it and is predicted here.
     ["test_below_floor_is_unknown_too",
      "test_an_absent_lane_file_is_unknown_as_well",
      "test_the_consumable_floor_cell_is_unknown_and_never_a_no"]),

    ("M9",
     "an UNKNOWN beside a False is reported as a DISAGREEMENT rather than "
     "as an absence",
     [('        "verdicts_disagree": (below is not None and below_raw is '
       'not None\n                              and below != below_raw),',
       '        "verdicts_disagree": below != below_raw,')],
     ["test_below_floor_is_unknown_too"]),

    ("M10",
     "an UNKNOWN lane is counted in the consumable denominator, so a total "
     "over a subset reads as a total over the estate",
     [('    out["consumable_lanes"] = len(known_use)',
       '    out["consumable_lanes"] = len(rows)')],
     ["test_an_unknown_lane_is_in_neither_total",
      "test_the_denominator_is_printed_with_every_total"]),

    ("M11",
     "the locked brief is reported as RUNNING, which is the nearest "
     "available name and the wrong one",
     [("    locked = inflight if watcher == W_DEAD else []\n"
       "    running = inflight if watcher == W_LIVE else []",
       "    locked = []\n    running = inflight")],
     ["test_the_locked_brief_is_named_under_its_own_heading",
      "test_it_is_not_counted_as_running",
      "test_the_lane_is_stranded_and_the_brief_is_reported_estate_wide",
      "test_liveness_unknown_places_it_in_neither",
      "test_qwens_locked_brief_is_named_and_counted_nowhere_else",
      "test_the_whole_estate_renders_without_one_healthy_lane"]),

    ("M12",
     "a dead watcher with an empty queue is reported STRANDED, so a lane "
     "a restart would leave starved reads as one with work waiting",
     [("        state = S_STRANDED if (raw or 0) > 0 or locked "
       "else S_DEAD_EMPTY",
       "        state = S_STRANDED")],
     ["test_a_dead_watcher_with_an_empty_queue_is_not_stranded"]),

    ("M13",
     "a brief whose filename carries no TASK id is counted as consumable "
     "work instead of taking the lane to UNKNOWN",
     [('            out["unnamed"].append(name)\n            continue',
       "            continue")],
     ["test_a_brief_with_no_task_id_takes_the_lane_to_unknown"]),
)

RUNNER = """
import json, sys, unittest
loader = unittest.TestLoader()
suite = loader.loadTestsFromNames([%r])
result = unittest.TextTestRunner(verbosity=0, stream=sys.stderr).run(suite)
names = sorted({test.id().rsplit(".", 1)[-1]
                for test, _ in list(result.failures) + list(result.errors)})
sys.stdout.write("KILLSET " + json.dumps(
    {"ran": result.testsRun, "names": names,
     "loader_errors": bool(loader.errors)}) + "\\n")
"""


def md5(path):
    with open(path, "rb") as handle:
        return hashlib.md5(handle.read()).hexdigest()


def run_module():
    """`(ran, failing names, loader_errors)` straight off the result object.

    NOT parsed from `-v` output: `unittest -v` wraps a long test name across
    two lines and this module's names are long, so a text reader reports a
    wrapped name as absent - which reads exactly like a mutation that killed
    nothing. The result object cannot wrap.
    """
    code = "import os, sys\nsys.path.insert(0, %r)\n%s" % (ROOT,
                                                           RUNNER % MODULE)
    done = subprocess.run([sys.executable, "-c", code], cwd=ROOT,
                          capture_output=True, text=True, timeout=900)
    for line in done.stdout.splitlines():
        if line.startswith("KILLSET "):
            payload = json.loads(line[len("KILLSET "):])
            return payload["ran"], payload["names"], payload["loader_errors"]
    raise AssertionError("no KILLSET line.\nstdout:\n%s\nstderr:\n%s"
                         % (done.stdout[-2000:], done.stderr[-3000:]))


def apply_edits(edits):
    with open(TARGET, encoding="utf-8") as handle:
        text = handle.read()
    for before, after in edits:
        found = text.count(before)
        if found != 1:
            raise AssertionError("the mutation's anchor occurs %d times, not "
                                 "once:\n%r" % (found, before))
        text = text.replace(before, after)
    with open(TARGET, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def main():
    pristine = md5(TARGET)
    backup = os.path.join(tempfile.mkdtemp(prefix="depth-mut-"),
                          "queuedepth.py")
    shutil.copyfile(TARGET, backup)
    assert md5(backup) == pristine

    print("TARGET   %s" % os.path.relpath(TARGET, ROOT))
    print("PRISTINE md5 %s" % pristine)
    print("BACKUP   md5 %s  (byte copy; the revert is a copy back, never a "
          "git checkout)" % md5(backup))
    print()

    ran, failing, loader_errors = run_module()
    print("BASELINE: %d tests, %d failing, loader_errors=%s"
          % (ran, len(failing), loader_errors))
    if failing or loader_errors:
        print("  the baseline is not green, so no kill-set below means "
              "anything. Names: %r" % failing)
        return 1
    baseline = set()
    print("  GREEN. Every name below is therefore this mutation's own.")
    print()

    verdicts = []
    for name, what, edits, predicted in MUTATIONS:
        try:
            apply_edits(edits)
            changed = md5(TARGET)
            assert changed != pristine, "the edit did not change the file"
            ran, failing, loader_errors = run_module()
        finally:
            shutil.copyfile(backup, TARGET)
            restored = md5(TARGET)
        killed = set(failing) - baseline
        want = set(predicted)
        row = {"name": name, "what": what, "ran": ran,
               "killed": sorted(killed),
               "predicted_and_killed": sorted(want & killed),
               "predicted_but_survived": sorted(want - killed),
               "killed_but_not_predicted": sorted(killed - want),
               "loader_errors": loader_errors,
               "reverted_md5_matches": restored == pristine}
        verdicts.append(row)

        print("%s  %s" % (name, what))
        print("    mutated md5 %s   reverted md5 %s   MATCHES PRISTINE: %s"
              % (changed, restored, row["reverted_md5_matches"]))
        if loader_errors:
            print("    THE MODULE DID NOT IMPORT. A mutation that breaks the "
                  "import kills every test for the wrong reason and this "
                  "kill-set is void.")
        print("    KILL-SET (%d): %s"
              % (len(killed), ", ".join(sorted(killed)) or "NOTHING"))
        if row["predicted_but_survived"]:
            print("    ** SURVIVED AND WAS PREDICTED TO DIE - a missing "
                  "test: %s" % ", ".join(row["predicted_but_survived"]))
        if row["killed_but_not_predicted"]:
            print("    (collateral, not counted as a win: %s)"
                  % ", ".join(row["killed_but_not_predicted"]))
        if not killed:
            print("    ** WATCHED BY NOTHING. The guard this edit removes is "
                  "not observed by any test in this module.")
        print()

    ran, failing, loader_errors = run_module()
    print("AFTER ALL MUTATIONS: %d tests, %d failing, file md5 %s, matches "
          "pristine: %s" % (ran, len(failing), md5(TARGET),
                            md5(TARGET) == pristine))

    survived = [row["name"] for row in verdicts if not row["killed"]]
    missing = [(row["name"], row["predicted_but_survived"])
               for row in verdicts if row["predicted_but_survived"]]
    bad_revert = [row["name"] for row in verdicts
                  if not row["reverted_md5_matches"]]
    print()
    print("SUMMARY: %d mutations, %d watched by nothing, %d with a predicted "
          "kill that survived, %d reverts that did not match pristine."
          % (len(verdicts), len(survived), len(missing), len(bad_revert)))
    if survived:
        print("  watched by nothing: %s" % ", ".join(survived))
    for name, names in missing:
        print("  %s predicted but survived: %s" % (name, ", ".join(names)))
    if bad_revert:
        print("  REVERT FAILED: %s" % ", ".join(bad_revert))
        return 1

    # THE PAIR, STATED AS THE BRIEF ASKS FOR IT. Each direction's kill-set
    # by name, and the three controls' membership of it.
    print()
    print("THE PAIRED DIRECTION (C6):")
    for name in ("M5", "M6"):
        row = [item for item in verdicts if item["name"] == name][0]
        print("  %s %s\n     kill-set: %s"
              % (name, row["what"], ", ".join(row["killed"]) or "NOTHING"))
    shutil.rmtree(os.path.dirname(backup), ignore_errors=True)
    return 0 if not (failing or loader_errors) else 1


if __name__ == "__main__":
    raise SystemExit(main())
