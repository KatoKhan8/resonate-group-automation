"""TASK-123: mechanically diff the failing test list by name.

Reads the suite_run.log, extracts FAIL/ERROR names, sorts them, and diffs
against the two reference lists. Never eyeball - always sort and diff.
"""
import re
import sys
import os


def extract_failures(log_path):
    """Extract failure names from suite_run.log."""
    failures = []
    with open(log_path, "r", errors="replace") as f:
        in_failure_section = False
        for line in f:
            stripped = line.strip()
            if stripped.startswith("=" * 40):
                in_failure_section = True
                continue
            if stripped.startswith("-" * 70):
                in_failure_section = False
                continue
            if in_failure_section and (stripped.startswith("FAIL: ") or stripped.startswith("ERROR: ")):
                failures.append(stripped)
    return sorted(failures)


def extract_test_count(log_path):
    """Extract the 'Ran N tests' line."""
    with open(log_path, "r", errors="replace") as f:
        for line in f:
            if line.strip().startswith("Ran "):
                return line.strip()
    return "unknown"


def extract_result_line(log_path):
    """Extract the FAILED/OK line."""
    with open(log_path, "r", errors="replace") as f:
        lines = f.readlines()
    for line in reversed(lines[-50:]):
        stripped = line.strip()
        if stripped.startswith("FAILED") or stripped == "OK":
            return stripped
    return "unknown"


# The 11 from TASK-088 (the STILL RED list)
REFERENCE_11 = sorted([
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
])

# The 12 from the final run = REFERENCE_11 + test_five_step_purposes_unchanged
REFERENCE_12 = sorted(REFERENCE_11 + [
    "tests.test_eight_step_cadence.TestBothCadencesSelectableByName.test_five_step_purposes_unchanged",
])


def normalise_name(failure_line):
    """Strip 'FAIL: ' or 'ERROR: ' prefix to get the test name."""
    for prefix in ("FAIL: ", "ERROR: "):
        if failure_line.startswith(prefix):
            return failure_line[len(prefix):].strip()
    return failure_line.strip()


def diff_failures(current_failures):
    current_names = sorted(normalise_name(f) for f in current_failures)

    ref_11_names = set(REFERENCE_11)
    ref_12_names = set(REFERENCE_12)
    current_set = set(current_names)

    fixed_vs_11 = ref_11_names - current_set
    still_red_vs_11 = ref_11_names & current_set
    introduced_vs_11 = current_set - ref_11_names

    fixed_vs_12 = ref_12_names - current_set
    still_red_vs_12 = ref_12_names & current_set
    introduced_vs_12 = current_set - ref_12_names

    print("=" * 60)
    print("CURRENT FAILURES (sorted by name)")
    print("=" * 60)
    for f in current_names:
        print(f"  {f}")
    print(f"\nTotal: {len(current_names)}")

    print("\n" + "=" * 60)
    print("DIFF vs TASK-088's 11")
    print("=" * 60)

    print(f"\nFIXED ({len(fixed_vs_11)}):")
    for name in sorted(fixed_vs_11):
        print(f"  {name}")

    print(f"\nSTILL RED ({len(still_red_vs_11)}):")
    for name in sorted(still_red_vs_11):
        print(f"  {name}")

    print(f"\nINTRODUCED ({len(introduced_vs_11)}):")
    for name in sorted(introduced_vs_11):
        print(f"  {name}")

    print("\n" + "=" * 60)
    print("DIFF vs final run's 12")
    print("=" * 60)

    print(f"\nFIXED ({len(fixed_vs_12)}):")
    for name in sorted(fixed_vs_12):
        print(f"  {name}")

    print(f"\nSTILL RED ({len(still_red_vs_12)}):")
    for name in sorted(still_red_vs_12):
        print(f"  {name}")

    print(f"\nINTRODUCED ({len(introduced_vs_12)}):")
    for name in sorted(introduced_vs_12):
        print(f"  {name}")


if __name__ == "__main__":
    log_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "scripts", "suite_run.log")
    if not os.path.exists(log_path):
        print(f"ERROR: {log_path} not found. Has the suite run?")
        sys.exit(1)

    print(f"Reading: {log_path}")
    print(f"Test count: {extract_test_count(log_path)}")
    print(f"Result: {extract_result_line(log_path)}")
    print()

    failures = extract_failures(log_path)
    diff_failures(failures)
