"""Mutate `src.lanerework` one edit at a time and name the kill-set each way.

WHY THE REVERT IS A BYTE BACKUP AND NOT `git checkout --`. This repository's
shared config sets `core.autocrlf=true` and clearing `GIT_CONFIG_SYSTEM` does
not turn that off, so a checkout in an LF tree rewrites every line ending
while `git status` goes on calling the file clean. The bytes would differ from
the bytes the measurement was taken against and nothing would say so. So the
pristine file is copied to a temporary path before anything is touched, every
revert is a byte copy back, and every revert is verified by md5 - the one
check that cannot be fooled by an index stat.

WHY EACH MUTATION IS RUN ALONE AND PREDICTED FIRST. A mutation whose kill-set
is merely non-empty proves nothing: a test that reddens for ANY edit to the
mutated file makes every mutation look killed. So each mutation declares the
tests it SHOULD kill, and the run reports three sets - predicted-and-killed,
predicted-and-SURVIVED, and killed-but-not-predicted. The second is a missing
test. The third is collateral, and it is printed rather than counted as a win.

C5 IS THE PAIR, and it is the reason this file exists at all: `0130` recorded
that its own C4 could not detect a classifier calling everything LOGGED, and
that the PAIR of controls was the real measurement. So `M2` calls everything
a re-dispatch and `M3` calls nothing one, and both kill-sets are named.

    py -3 scripts/rework_mutations.py
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(ROOT, "src", "lanerework.py")
MODULE = "tests.test_a_finished_brief_dispatched_again_is_counted"

#: Short names for the tests, so a kill-set reads as a sentence rather than
#: as four lines of dotted path. Keyed on the method name, which is unique
#: across this module.
C1 = "C1ClosedBeforeTheStart"
C2 = "C2ClosedAfterTheStart"
C3 = "C3NoEntryAtAll"
C4 = "C4EntryWithNoReadableCloseTime"


#: `(name, what it breaks, [(before, after), ...], [predicted kills])`.
#: Every `before` must occur EXACTLY ONCE in the file; the harness refuses
#: the mutation otherwise, because a replace that hit two sites is two
#: mutations and the kill-set would not say which one was observed.
MUTATIONS = (
    ("M1",
     "an undatable entry falls back to 'not a re-dispatch' - the exact "
     "fallback C4 exists to forbid",
     [('    row["verdict"] = UNDATED if undatable else FRESH',
       '    row["verdict"] = FRESH')],
     # `test_c4_the_entry_was_found_and_only_its_date_was_not` was predicted
     # here on the first run and SURVIVED, and it was right to: it asserts
     # the entry was found and the placements are UNDATABLE, and reads no
     # verdict at all. The prediction was wrong, not the test. What the
     # survivor did expose is that nothing observed the ESTATE rollup -
     # `rework()` buckets by verdict membership in its own loop, separate
     # from the lane tally - so `..._files_it_as_unknown_and_not_as_clean`
     # was written and is predicted below.
     ["test_c4_the_verdict_is_undated",
      "test_c4_undated_is_unknown_and_never_clean",
      "test_c4_the_estate_rollup_files_it_as_unknown_and_not_as_clean",
      "test_a_future_re_dispatch_is_not_a_declaration",
      "test_a_commit_whose_subject_names_another_lane_is_refused",
      "test_a_citing_line_that_names_another_lane_is_refused",
      "test_a_commit_not_naming_this_task_is_not_evidence_about_it",
      "test_a_declaration_convicts_only_the_last_start_of_a_brief"]),

    ("M2",
     "C5, direction one: EVERYTHING is a re-dispatch",
     [('        row["verdict"] = NO_ENTRY\n        return row',
       '        row["verdict"] = REWORK\n        return row'),
      ('    row["verdict"] = UNDATED if undatable else FRESH',
       '    row["verdict"] = REWORK')],
     ["test_c2_the_verdict_is_fresh",
      "test_c2_fresh_is_not_unknown_and_not_rework",
      "test_c3_the_verdict_is_no_entry",
      "test_c3_is_not_rework_and_not_unknown",
      "test_c3_is_a_state_of_its_own_and_not_merged_into_fresh",
      "test_c3_limit_is_counted_with_its_denominator"]),

    ("M3",
     "C5, direction two: NOTHING is a re-dispatch",
     [("    if best is not None:\n        entry, field, value, detail, "
       "attribution = best",
       "    if False:\n        entry, field, value, detail, "
       "attribution = best"),
      ("    if declared is not None:\n        # No clock reached it",
       "    if False:\n        # No clock reached it")],
     ["test_c1_the_verdict_is_rework",
      "test_c1_names_the_entry_the_field_and_the_value",
      "test_c1_the_cost_is_the_dispatched_runs_own_elapsed_time",
      "test_c1_the_tally_counts_it_once_against_one_start",
      "test_c6_all_six_are_recovered_as_re_dispatches",
      "test_c6_each_is_convicted_by_the_rung_the_record_names",
      "test_c6_the_cost_of_each_matches_the_watchers_own_clock",
      "test_c6_0235_is_convicted_a_second_time_by_its_heading_alone"]),

    ("M4",
     "the commit rung stops refusing a commit whose subject names another "
     "lane",
     [("        subject_other = lane_tokens(row[\"subject\"], lane, known)\n"
       "        if subject_other:\n            continue",
       "        subject_other = lane_tokens(row[\"subject\"], lane, known)\n"
       "        if False:\n            continue")],
     ["test_a_commit_whose_subject_names_another_lane_is_refused"]),

    ("M5",
     "the commit rung stops refusing a citing line that names another lane",
     [("        if lines and not clean:\n            continue",
       "        if False:\n            continue")],
     ["test_a_citing_line_that_names_another_lane_is_refused"]),

    ("M6",
     "the lane-name boundary excludes a trailing hyphen again - the real "
     "defect this task found, which made the refusal inert on every "
     "`task-<lane>-<date>` branch",
     [('                             + r"(?![0-9a-z])")',
       '                             + r"(?![0-9a-z-])")')],
     ["test_the_longer_lane_name_is_matched_first"]),

    ("M7",
     "the lane's own declaration is ignored",
     [("    if _NOT_A_DECLARATION.search(text or \"\"):\n        return False",
       "    if True:\n        return False")],
     ["test_a_declaration_convicts_even_when_its_own_range_is_after",
      "test_a_declaration_convicts_only_the_last_start_of_a_brief"]),

    ("M8",
     "an ABSENT lane file reads as an authority that answered 'no entries'",
     [("    if lane_state in (lanes.ABSENT, lanes.UNREADABLE):",
       "    if lane_state in (lanes.UNREADABLE,):")],
     ["test_an_unreadable_lane_file_is_unreadable_too"]),

    ("M9",
     "an approximate time is bounded at its stated minute rather than at "
     "the end of its hour",
     [("        return hour, 59, 59, bool(match.group(prefix + \"zulu\"))\n"
       "    if minute.isdigit():",
       "        return hour, 0, 0, bool(match.group(prefix + \"zulu\"))\n"
       "    if minute.isdigit():")],
     ["test_an_approximate_time_is_bounded_at_the_end_of_its_hour",
      "test_c6_0235_is_convicted_a_second_time_by_its_heading_alone"]),

    ("M10",
     "a `Z` suffix is not converted to local time",
     [("        when += datetime.timedelta(hours=offset_hours)",
       "        when += datetime.timedelta(hours=0)")],
     ["test_a_zulu_range_is_converted_with_the_measured_offset",
      "test_an_approximate_time_is_bounded_at_the_end_of_its_hour",
      "test_c6_0235_is_convicted_a_second_time_by_its_heading_alone"]),

    ("M11",
     "an entry's block runs to end of file, so every entry is handed every "
     "SHA in the lane file",
     [('            if later["level"] <= item["level"]:',
       '            if False:')],
     ["test_a_deeper_heading_stays_inside_its_entry"]),

    ("M12",
     "a declaration convicts every START of its brief, not only the last",
     [("                           declared_allowed=last_start.get(task) "
       "== index)",
       "                           declared_allowed=True)")],
     ["test_a_declaration_convicts_only_the_last_start_of_a_brief"]),

    ("M13",
     "the date rung decides on the same day, so an undatable same-day "
     "entry is ordered by a bound it does not have",
     [('        if day < start_when.date():',
       '        if day <= start_when.date():')],
     ["test_a_date_alone_decides_only_across_a_day_boundary",
      "test_c4_the_verdict_is_undated",
      "test_c4_undated_is_unknown_and_never_clean",
      "test_c4_the_entry_was_found_and_only_its_date_was_not"]),
)

RUNNER = """
import json, sys, unittest
loader = unittest.TestLoader()
suite = loader.loadTestsFromNames([%r])
result = unittest.TextTestRunner(verbosity=0, stream=open(os.devnull, "w")
                                 if False else sys.stderr).run(suite)
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

    NOT parsed from `-v` output. `unittest -v` wraps a long test name across
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
    backup = os.path.join(tempfile.mkdtemp(prefix="rework-mut-"),
                          "lanerework.py")
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
    shutil.rmtree(os.path.dirname(backup), ignore_errors=True)
    return 0 if not (failing or loader_errors) else 1


if __name__ == "__main__":
    raise SystemExit(main())
