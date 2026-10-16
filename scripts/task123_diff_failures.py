#!/usr/bin/env python3
"""TASK-123: diff failing tests by name against historical lists.

Reads the suite verdict/log and compares against:
- The 11 from TASK-088
- Reports FIXED, STILL RED, and INTRODUCED

## IT READ 228 FAILURES AS ELEVEN FIXED. Measured 2026-10-16, TASK-0300.

Against `scripts/suite_verdict.txt` at `status=FAIL`, `failures=228`, 228 name
lines, this script printed `FIXED (11)`, `STILL RED (0)`, `Current failures: 1`.
Three separate defects stacked, and each one on its own would have been enough:

1. The extractor was `re.search(r'\\(([^)]+)\\)\\s*$', line)` - it required a
   line to END in a parenthesis. A verdict's name lines are `  FAIL: dotted.name`
   and have none, so all 228 were skipped. The one line in the file that does
   end in `)` is `result_line=`, so the script's single "test name" was the
   string `failures=163, errors=68, skipped=19, expected failures=18`.
2. No prefix normalisation. `TASK088_ELEVEN` is spelled `tests.test_x.C.t` and a
   verdict spells the same test `test_x.C.t`, so even a correct extractor would
   have reported all eleven FIXED and all 228 INTRODUCED. The real answer is
   6 still red. `suite_baseline.strip_prefix` already existed for exactly this
   and was not used; it is used here now rather than copied.
3. Nothing it could not read was ever an error. A verdict with no `result_line`
   - which is every TIMED-OUT verdict, because `run_suite._find_result_line`
   searches only the last 30 lines - yielded zero names and printed
   "No failures found - suite may have passed!" with exit 0.

So the rule this file now keeps, which is the house rule everywhere else:
**an input this script cannot read is never zero failures.** It parses the
verdict's own header keys, cross-checks the names it found against the
`failures=` the verdict declares, and REFUSES - naming the key or the state -
rather than reporting a reassuring number about a file it did not understand.

EXIT CODES follow `src/stopwatchdog.py`'s three, for the same reason that file
gives: an answer this script has not understood must never read as a pass.

    0  zero failures, POSITIVELY established (declared 0 and listed none)
    1  failures present, and the diff below is about them
    2  could not read the input - partial, inconsistent, or an unknown format

The old code exited 0 for all three of those. It also died at the `FIXED` list
with a UnicodeEncodeError, because the tick glyph it printed does not exist in
cp1250, which is this machine's console codec; the markers are ASCII now.
"""
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import suite_baseline  # noqa: E402  - sibling script, not a package

#: `0` PASS, `1` STOP, `2` BLIND. See the module docstring.
CLEAN = 0
FAILURES_PRESENT = 1
CANNOT_READ = 2

# The 11 from TASK-088 (recorded in docs/qwen-tasks/REVIEW/TASK-088-*.md)
TASK088_ELEVEN = {
    "tests.test_ingest.TestPhase1Csv.test_every_dropped_record_carries_its_reason",
    "tests.test_ingest.TestPhase1Csv.test_queue_has_a_record_for_every_row",
    "tests.test_no_write_happens_without_every_gate.TheAccountIsAskedToo.test_a_finished_campaign_with_no_reply_still_authorizes",
    "tests.test_a_bounced_address_stops_being_sendable.TheSENDPathReadsIt.test_decide_blocks_a_bounced_address",
    "tests.test_replaysim.TestThePositiveChain.test_the_company_is_paused_afterwards",
    "tests.test_replaysim.TestTheScenarios.test_each_one_classifies_as_documented",
    "tests.test_referral.TheWholeChain.test_a_plain_hand_off_holds_the_referrer",
    "tests.test_mutation_anchors.EveryAnchorStillMatches.test_every_guard_appears_exactly_once",
    "tests.test_fixture_hygiene.TestKnownSets.test_every_phone_number_is_a_reserved_fiction",
    "tests.test_fixture_hygiene.TestNoRealDataAnywhereInGit.test_every_email_address_is_on_a_reserved_domain",
    "tests.test_fixture_hygiene.TestNoRealDataAnywhereInGit.test_no_real_person_or_client_named",
}

#: The verdict's header, as `scripts/run_suite.py` writes it: bare `key=value`
#: at column 0, before any name line.
_HEADER = re.compile(r"^([a-z_]+)=(.*)$")

#: The verdict's name lines: exactly two spaces, the kind, the dotted path.
#: Anchored at both ends, because an unanchored read of a verdict is how
#: `run_suite._parse_failures` came to invent a name (TASK-0290).
_VERDICT_NAME = re.compile(r"^ {2}(FAIL|ERROR): (\S+)\s*$")

#: What a verdict must carry before anything may be concluded from it. A key
#: that is absent is not a key whose value is zero.
REQUIRED_KEYS = ("status", "failures", "failures_are_partial")

#: A run that printed this finished; its absence means the log describes only
#: the part that ran. Same contract as `run_suite._RAN`.
_RAN = re.compile(r"^Ran \d+ tests?", re.M)
_TERMINAL = re.compile(r"^(OK|FAILED)(\s|\(|$)")

EXPECTED_VERDICT_FORMAT = (
    "a verdict written by scripts/run_suite.py: bare `key=value` lines at "
    "column 0 carrying at least " + ", ".join(REQUIRED_KEYS) + ", then one "
    "`  FAIL: dotted.name` or `  ERROR: dotted.name` line per failing test")


class CannotRead(Exception):
    """The input did not answer the question. Never a count, never a zero."""


def extract_failures_from_verdict(verdict_path):
    """Failing names from `suite_verdict.txt`, prefix-normalised.

    Raises `CannotRead` rather than returning a short or empty set, because
    every caller of this function turns its length into a number somebody
    acts on.
    """
    with open(verdict_path, "r", encoding="utf-8", errors="replace") as fh:
        text = fh.read()

    header = {}
    for line in text.splitlines():
        m = _HEADER.match(line)
        if m:
            header.setdefault(m.group(1), m.group(2).strip())

    missing = [k for k in REQUIRED_KEYS if k not in header]
    if missing:
        raise CannotRead(
            "the verdict carries no %s key. Expected %s"
            % (" and no ".join(missing), EXPECTED_VERDICT_FORMAT))

    try:
        declared = int(header["failures"])
    except ValueError:
        raise CannotRead(
            "failures=%r is not a number. Expected %s"
            % (header["failures"], EXPECTED_VERDICT_FORMAT))

    if header["status"] == "INCOMPLETE" or header["failures_are_partial"] != "False":
        raise CannotRead(
            "this run did not finish - status=%s, failures_are_partial=%s. "
            "Its %d name(s) cover only the tests it reached, so every test it "
            "never ran would read as FIXED. A partial list is not a baseline."
            % (header["status"], header["failures_are_partial"], declared))

    names = set()
    for line in text.splitlines():
        m = _VERDICT_NAME.match(line)
        if m:
            names.add(suite_baseline.strip_prefix(m.group(2)))

    if len(names) != declared:
        raise CannotRead(
            "the verdict declares failures=%d and lists %d distinct name(s). "
            "Two authorities for one number, so neither is used."
            % (declared, len(names)))

    return names


def extract_failures_from_log(log_path):
    """Failing names from `suite_run.log`, via the canonical parser.

    `suite_baseline.parse_failures` reads the closing `FAIL:`/`ERROR:` blocks
    and already strips the prefix and the subtest suffix. It is only asked
    once the log has been shown to have FINISHED: on a killed run those blocks
    were never printed, and zero blocks in a log that stops mid-run is not
    zero failures.
    """
    with open(log_path, "r", encoding="utf-8", errors="replace") as fh:
        text = fh.read()

    if not _RAN.search(text):
        raise CannotRead(
            "the log has no `Ran N tests` line, so the run did not finish and "
            "its closing failure blocks were never printed. Zero blocks here "
            "is not zero failures.")
    if not any(_TERMINAL.match(l.strip()) for l in text.splitlines()[-40:]):
        raise CannotRead(
            "the log has no terminal OK / FAILED line in its last 40 lines, "
            "so it was truncated after `Ran N tests`.")

    return set(suite_baseline.parse_failures(text))


def main():
    project_root = Path(__file__).parent.parent
    verdict_path = project_root / "scripts" / "suite_verdict.txt"
    log_path = project_root / "scripts" / "suite_run.log"

    # Try verdict file first, fall back to log
    if verdict_path.exists():
        print(f"Reading from: {verdict_path}")
        reader = extract_failures_from_verdict
        source = verdict_path
    elif log_path.exists():
        print(f"Reading from: {log_path}")
        reader = extract_failures_from_log
        source = log_path
    else:
        print("REFUSED: no suite_verdict.txt and no suite_run.log found")
        print("Run the suite first: py -3 scripts/run_suite.py")
        return CANNOT_READ

    try:
        current_failures = reader(source)
    except CannotRead as exc:
        print(f"\nREFUSED: {exc}")
        print("\nThis script reports no number it cannot establish. Exit "
              f"{CANNOT_READ} means UNREAD, which is not zero failures and "
              "not a pass.")
        return CANNOT_READ

    baseline = {suite_baseline.strip_prefix(n) for n in TASK088_ELEVEN}

    if not current_failures:
        print("\nZERO FAILURES, positively established: the verdict declares "
              "failures=0 and lists no names.")
        print(f"\nTASK-088 baseline:  {len(baseline)} tests")
        print(f"Fixed:              {len(baseline)} tests")
        return CLEAN

    print(f"\nCurrent failures: {len(current_failures)}")
    for name in sorted(current_failures):
        print(f"  {name}")

    # Diff against TASK-088's 11. Both sides are prefix-normalised: the
    # baseline is spelled `tests.test_x.C.t` and a verdict spells the same
    # test `test_x.C.t`, and a diff whose two sides spell one test two ways
    # reports every entry as both gone and new.
    fixed = baseline - current_failures
    still_red = baseline & current_failures
    introduced = current_failures - baseline

    print(f"\n{'='*70}")
    print("DIFF AGAINST TASK-088'S 11")
    print(f"{'='*70}")

    print(f"\nFIXED ({len(fixed)}):")
    if fixed:
        for name in sorted(fixed):
            print(f"  [fixed]     {name}")
    else:
        print("  (none)")

    print(f"\nSTILL RED ({len(still_red)}):")
    if still_red:
        for name in sorted(still_red):
            print(f"  [still red] {name}")
    else:
        print("  (none)")

    print(f"\nINTRODUCED ({len(introduced)}):")
    if introduced:
        for name in sorted(introduced):
            print(f"  [new]       {name}")
    else:
        print("  (none)")

    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    print(f"TASK-088 baseline:  {len(baseline)} tests")
    print(f"Current failures:   {len(current_failures)} tests")
    print(f"Fixed:              {len(fixed)} tests")
    print(f"Still red:          {len(still_red)} tests")
    print(f"Introduced:         {len(introduced)} tests")

    return FAILURES_PRESENT


if __name__ == "__main__":
    sys.exit(main())
