#!/usr/bin/env python3
"""TASK-123: diff failing tests by name against historical lists.

Reads the suite verdict/log and compares against:
- The 11 from TASK-088
- Reports FIXED, STILL RED, and INTRODUCED
"""
import re
import sys
from pathlib import Path

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


def extract_failures_from_verdict(verdict_path):
    """Extract failure names from suite_verdict.txt."""
    failures = set()
    with open(verdict_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            # Match lines like: "FAIL: test_name (module.Class.test_name)"
            # or "ERROR: test_name (module.Class.test_name)"
            match = re.search(r'\(([^)]+)\)\s*$', line)
            if match:
                full_name = match.group(1)
                failures.add(full_name)
    return failures


def extract_failures_from_log(log_path):
    """Extract failure names from suite_run.log as fallback."""
    failures = set()
    in_failure_section = False
    
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip()
            
            # Detect start of failure details section
            if line.startswith("=" * 40):
                in_failure_section = True
                continue
            
            # Detect end of failure details section
            if line.startswith("-" * 70):
                in_failure_section = False
                continue
            
            # Extract failure names from the details section
            if in_failure_section:
                # Match lines like: "FAIL: test_name (module.Class.test_name)"
                # or "ERROR: test_name (module.Class.test_name)"
                match = re.match(r'^(?:FAIL|ERROR):\s+\S+\s+\(([^)]+)\)', line)
                if match:
                    full_name = match.group(1)
                    failures.add(full_name)
    
    return failures


def main():
    project_root = Path(__file__).parent.parent
    verdict_path = project_root / "scripts" / "suite_verdict.txt"
    log_path = project_root / "scripts" / "suite_run.log"
    
    # Try verdict file first, fall back to log
    if verdict_path.exists():
        print(f"Reading from: {verdict_path}")
        current_failures = extract_failures_from_verdict(verdict_path)
    elif log_path.exists():
        print(f"Reading from: {log_path}")
        current_failures = extract_failures_from_log(log_path)
    else:
        print("ERROR: No suite_verdict.txt or suite_run.log found")
        print("Run the suite first: py -3 scripts/run_suite.py")
        return 1
    
    if not current_failures:
        print("No failures found - suite may have passed!")
        return 0
    
    print(f"\nCurrent failures: {len(current_failures)}")
    for name in sorted(current_failures):
        print(f"  {name}")
    
    # Diff against TASK-088's 11
    fixed = TASK088_ELEVEN - current_failures
    still_red = TASK088_ELEVEN & current_failures
    introduced = current_failures - TASK088_ELEVEN
    
    print(f"\n{'='*70}")
    print("DIFF AGAINST TASK-088'S 11")
    print(f"{'='*70}")
    
    print(f"\nFIXED ({len(fixed)}):")
    if fixed:
        for name in sorted(fixed):
            print(f"  ✓ {name}")
    else:
        print("  (none)")
    
    print(f"\nSTILL RED ({len(still_red)}):")
    if still_red:
        for name in sorted(still_red):
            print(f"  ✗ {name}")
    else:
        print("  (none)")
    
    print(f"\nINTRODUCED ({len(introduced)}):")
    if introduced:
        for name in sorted(introduced):
            print(f"  + {name}")
    else:
        print("  (none)")
    
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    print(f"TASK-088 baseline:  {len(TASK088_ELEVEN)} tests")
    print(f"Current failures:   {len(current_failures)} tests")
    print(f"Fixed:              {len(fixed)} tests")
    print(f"Still red:          {len(still_red)} tests")
    print(f"Introduced:         {len(introduced)} tests")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
