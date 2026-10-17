"""Mutation proof for POOL 0005.

Reverts the fix in `scripts/batch_linkedin_push.py`, runs the test,
demonstrates the bad outcome (stranger's list id reaches create_campaign),
then re-applies the fix and demonstrates the safe outcome.

The revert and re-apply both change the file SIZE, and __pycache__ is
purged between each run so .pyc invalidation cannot mask the change.
"""
import os
import subprocess
import sys
import time


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "scripts", "batch_linkedin_push.py")
PYCACHE = os.path.join(ROOT, "scripts", "__pycache__")


def purge_pycache():
    if os.path.isdir(PYCACHE):
        for name in os.listdir(PYCACHE):
            if name.startswith("batch_linkedin_push"):
                path = os.path.join(PYCACHE, name)
                try:
                    os.remove(path)
                except OSError:
                    pass


def read():
    with open(SCRIPT, "rb") as handle:
        return handle.read()


def write(data):
    with open(SCRIPT, "wb") as handle:
        handle.write(data)


def run_tests(label):
    print(f"\n{'=' * 70}\n{label}\n{'=' * 70}")
    purge_pycache()
    result = subprocess.run(
        [sys.executable, "-m", "unittest",
         "tests.test_heyreach_reuse_requires_ownership", "-v"],
        cwd=ROOT, capture_output=True, text=True)
    # Print the tail of stdout so we see the test verdicts and the
    # script's own print output.
    combined = result.stdout + "\n--- stderr ---\n" + result.stderr
    tail = combined[-4500:] if len(combined) > 4500 else combined
    print(tail)
    return result.returncode


# The marker strings we look for in the fixed file. These are the TEXT
# anchors, encoded as UTF-8 byte patterns at runtime so the non-ASCII
# operator quote survives.
MARKER_BUILD_START = "CLAIMED LIST IDS: every linkedin_list_id value".encode()
MARKER_BUILD_END = "existing_lists = {}".encode()
MARKER_IF_NEW = "if list_id and list_id in claimed_list_ids:".encode()
MARKER_IF_OLD = "if list_id:".encode()
MARKER_IF_LOG_STRANGER = "a list named ".encode()


def revert_to_old(data: bytes) -> bytes:
    """Strip the claimed_list_ids build and change the if back to the OLD check.

    Returns the mutated bytes. Raises ValueError if the expected patterns
    are not found (in which case the file is not modified).
    """
    # 1. Strip the claimed_list_ids build. Locate the comment block by
    #    its opening marker and remove everything up to and including the
    #    blank line before `existing_lists = {}`.
    build_start = data.find(MARKER_BUILD_START)
    if build_start < 0:
        raise ValueError("CLAIMED LIST IDS marker not found")
    # Back up to the start of the comment line (4 spaces + #).
    line_start = data.rfind(b"\n", 0, build_start) + 1
    build_end = data.find(MARKER_BUILD_END, build_start)
    if build_end < 0:
        raise ValueError("existing_lists = {} marker not found")
    # Walk back to the start of the line containing `existing_lists = {}`
    # so we keep its leading whitespace.
    build_line_start = data.rfind(b"\n", 0, build_end) + 1
    # Remove bytes [line_start, build_line_start) - this strips the
    # comment block AND the build loop, preserving the indent of the
    # `existing_lists = {}` line.
    mutated = data[:line_start] + data[build_line_start:]

    # 2. Replace the new if check with the old one. The original line is:
    #                if list_id and list_id in claimed_list_ids:
    # and the OLD code was simply:
    #                if list_id:
    # Same indent (16 spaces); only the predicate changes.
    new_if = MARKER_IF_NEW
    old_if = b"if list_id:"
    if new_if not in mutated:
        raise ValueError("new if check not found")
    mutated = mutated.replace(new_if, old_if, 1)

    # 3. Strip the inner `if list_id:` block that logs about the
    #    stranger's list - the OLD code had no such block. Locate the
    #    block by its opening comment and remove everything from the
    #    `if list_id:` line up to (but not including) the `# TASK 0210:`
    #    line which is the brake call.
    inner_if_marker = b"                    if list_id:\r\n                        # A list with our name"
    inner_if_marker_lf = b"                    if list_id:\n                        # A list with our name"
    inner_if_end_marker = b"                    # TASK 0210:"
    inner_start = mutated.find(inner_if_marker)
    if inner_start < 0:
        inner_start = mutated.find(inner_if_marker_lf)
    if inner_start >= 0:
        inner_end = mutated.find(inner_if_end_marker, inner_start)
        if inner_end >= 0:
            mutated = mutated[:inner_start] + mutated[inner_end:]

    return mutated


def main():
    original = read()
    original_size = len(original)
    print(f"Original script: {original_size} bytes")

    try:
        reverted = revert_to_old(original)
    except ValueError as exc:
        print(f"ABORT: {exc}")
        return 3
    if reverted == original:
        print("ABORT: revert did not change the file")
        return 3

    # Step 1: run with the fix, expect all 3 tests to PASS.
    rc_fix = run_tests("PHASE 1: FIX IN PLACE - expect 3 PASS")
    print(f"\nFix-phase exit code: {rc_fix}")
    if rc_fix != 0:
        print("ABORT: fix-phase did not pass cleanly; cannot prove mutation")
        return 2

    # Step 2: revert to OLD code. Wait a whole second so mtime advances.
    time.sleep(1.1)
    write(reverted)
    reverted_size = len(reverted)
    print(f"Reverted script: {reverted_size} bytes "
          f"(delta {reverted_size - original_size:+d})")

    # Step 3: run with OLD code, expect the bar test to FAIL.
    rc_old = run_tests("PHASE 2: FIX REVERTED - expect bar test to FAIL")
    print(f"\nReverted-phase exit code: {rc_old}")
    if rc_old == 0:
        print("ABORT: reverted-phase passed; the test does not see the defect")
        write(original)
        return 4

    # Step 4: restore the fix.
    time.sleep(1.1)
    write(original)
    restored = read()
    if restored != original:
        print("ABORT: restore did not reproduce the original bytes")
        return 5
    print(f"Restored script: {len(restored)} bytes (matches original)")

    # Step 5: run again with the fix, expect all 3 PASS.
    rc_restore = run_tests("PHASE 3: FIX RESTORED - expect 3 PASS again")
    print(f"\nRestore-phase exit code: {rc_restore}")
    if rc_restore != 0:
        print("ABORT: restore-phase did not pass; fix may not be intact")
        return 6

    print("\n" + "=" * 70)
    print("MUTATION PROOF COMPLETE.")
    print("  Phase 1 (fix in place):   PASS")
    print("  Phase 2 (fix reverted):   FAIL (the bar test saw the defect)")
    print("  Phase 3 (fix restored):   PASS")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
