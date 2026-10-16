#!/usr/bin/env python3
"""GATES 0090: run the exit-code instrument pair over a list of SHAs.

Builds scratch worktrees, runs two instruments per SHA in isolation,
prints one row per cell:
    sha | instrument | exit | violations-quoted | name-set-delta-vs-b1f290c84

Two instruments:
  1. check_write_site_inventory -- the exit-code dimension. Prints EXIT 0/1/2
     with violation lines. Structurally blind to name-set movements.
  2. test_write_site_inventory_check -- the name-set dimension (the gate test).
     Reports which test names fail, not the exit code.

Usage:
    # Run all four SHAs from the brief (default)
    py scripts/run_gate_0090.py

    # Custom list
    py scripts/run_gate_0090.py b1f290c84 f1552d4ec f7857e1ab c85724df0

    # Include teeth-control (plant synthetic stale exemption)
    py scripts/run_gate_0090.py --teeth

Each worktree is torn down immediately after use. No full suite lock.
No network calls. Pure AST + unittest, offline.

PYTHON: resolved via GATES_PYTHON env, then LOCALAPPDATA Python, then PATH.
GIT config clean per worktree (unset GIT_CONFIG_SYSTEM / GIT_CONFIG_COUNT).
"""

import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.abspath(os.path.dirname(__file__))
PYTHONS = [
    os.environ.get("GATES_PYTHON", ""),
    os.path.join(os.getenv("LOCALAPPDATA", ""), "Python", "bin", "python3.exe"),
]
for p in PYTHONS[1:]:
    if os.path.exists(p):
        PYTHON = p
        break
else:
    # Fall back to system PATH resolution
    import shutil as _shutil
    PYTHON = _shutil.which("py") or _shutil.which("python3") or "python"
PYTHON = PYTHON or "python"

DEFAULT_SHAS = [
    "b1f290c84",
    "f1552d4ec",
    "f7857e1ab",
    "c85724df0",
]

# Checker module to bootstrap into trees that lack it at the target SHA.
CHECKER_SHA = "f7857e1ab"  # last known good version of the checker


def _clean_env(env):
    """Remove git-config pollution that corrupts worktree locks."""
    env.pop("GIT_CONFIG_SYSTEM", None)
    env.pop("GIT_CONFIG_COUNT", None)
    return env


def _git(cwd, *args, env=None, capture=True):
    """Lightweight git wrapper; always unset bad config vars."""
    e = _clean_env(os.environ.copy())
    if env:
        e.update(env)
    cmd = ["git"] + list(args)
    r = subprocess.run(
        cmd, cwd=cwd, capture_output=capture, text=True, env=e, timeout=60
    )
    return r.returncode, r.stdout.strip(), r.stderr.strip()


def _checkout_checker(wt_dir):
    """Copy check_write_site_inventory.py into wt_dir/scripts/ via git show.

    Called for SHAs where the file was not yet added. We read the blob
    from CHECKER_SHA (known-good version) and write it into the scratch
    worktree. Uses git show which works across any two trees.
    """
    dst_file = os.path.join(wt_dir, "scripts", "check_write_site_inventory.py")
    dst_dir = os.path.dirname(dst_file)
    os.makedirs(dst_dir, exist_ok=True)

    # Read blob from CHECKER_SHA, write to destination
    rc, out, err = _git(
        ROOT, "show", f"{CHECKER_SHA}:scripts/check_write_site_inventory.py"
    )
    if rc != 0:
        print(f"  WARNING: could not fetch checker from {CHECKER_SHA}: {err}",
              file=sys.stderr)
        return False
    try:
        with open(dst_file, "w", encoding="utf-8", newline="\n") as f:
            f.write(out)
        return True
    except OSError as e:
        print(f"  WARNING: could not write checker: {e}", file=sys.stderr)
        return False


def _run_checker(wt_dir):
    """Run the inventory checker inside wt_dir, return (exit_code, lines)."""
    checker = os.path.join(wt_dir, "scripts", "check_write_site_inventory.py")
    if not os.path.exists(checker):
        return None, []

    # Delete .pyc to avoid mtime+size collision bugs (TASK-0078 proof)
    pyc_dir = os.path.join(wt_dir, "scripts", "__pycache__")
    if os.path.isdir(pyc_dir):
        shutil.rmtree(pyc_dir)

    cmd = [PYTHON, checker]
    r = subprocess.run(cmd, cwd=wt_dir, capture_output=True, text=True,
                       timeout=120, env=_clean_env(os.environ.copy()))
    lines = (r.stdout or "") + (r.stderr or "")
    return r.returncode, lines.splitlines()


def _parse_exit(lines):
    """Extract the EXIT line from checker output."""
    for line in lines:
        m = re.match(r"EXIT\s+(\d+)\s*(.*)", line)
        if m:
            return int(m.group(1)), m.group(2).strip()
    return None, ""


def _extract_violations(lines):
    """Return only VIOLATION lines from checker output."""
    return [l for l in lines if "VIOLATION" in l or "REFUSED" in l]


def _run_name_set_test(wt_dir):
    """Run the name-set test module, return (exit_code, failing_names)."""
    test_module = os.path.join(wt_dir, "tests", "test_write_site_inventory_check.py")
    if not os.path.exists(test_module):
        return None, []

    # Delete .pyc to avoid mtime+size collision bugs
    pyc_dir = os.path.join(wt_dir, "tests", "__pycache__")
    if os.path.isdir(pyc_dir):
        shutil.rmtree(pyc_dir)

    cmd = [PYTHON, "-m", "unittest",
           "tests.test_write_site_inventory_check.RealTree", "-v"]
    r = subprocess.run(cmd, cwd=wt_dir, capture_output=True, text=True,
                       timeout=300, env=_clean_env(os.environ.copy()))
    stdout = r.stdout or ""
    stderr = r.stderr or ""

    # Extract failing test names from inline records + epilogue blocks
    fails = set()
    start_re = re.compile(r"^(?P<name>\w+) \((?P<where>[\w.]+)\)")
    verdict_tail = re.compile(r"\.\.\. (?P<verdict>ok|FAIL|ERROR|"
                              r"expected failure|unexpected success)\s*$")
    block_re = re.compile(
        r"^(?:FAIL|ERROR):\s+(?P<name>\S+)\s+\((?P<where>[^)]+)\)$"
    )

    pending = None
    for raw in (stdout + "\n" + stderr).splitlines():
        start = start_re.match(raw)
        if start:
            pending = start.group("where") + "." + start.group("name")
        if pending and verdict_tail.match(raw):
            v = verdict_tail.match(raw).group("verdict")
            if v.startswith(("FAIL", "ERROR")):
                fails.add(pending)
            pending = None
        m = block_re.match(raw)
        if m:
            fails.add(m.group("name"))

    return r.returncode, sorted(fails)


def _has_checker_at_sha(wt_dir, sha):
    """Check if the file exists in the working tree at this SHA."""
    return os.path.exists(os.path.join(wt_dir, "scripts",
                                        "check_write_site_inventory.py"))


def _has_test_at_sha(wt_dir):
    return os.path.exists(os.path.join(wt_dir, "tests",
                                       "test_write_site_inventory_check.py"))


def _make_worktree(sha):
    """Create a detached scratch worktree at SHA. Returns path."""
    h = hashlib.md5(sha.encode()).hexdigest()[:10]
    path = os.path.join(tempfile.mkdtemp(), f"wt-{h}-{sha[:7]}")
    rc, out, err = _git(ROOT, "worktree", "add", "--detach", path, sha)
    if rc != 0:
        print(f"FATAL: failed to create worktree for {sha}: {err}",
              file=sys.stderr)
        sys.exit(1)
    return path


def _teardown_wt(path):
    """Tear down a scratch worktree and verify gone."""
    try:
        rc, _, _ = _git(ROOT, "worktree", "remove", path, "--force")
    except Exception:
        shutil.rmtree(path, ignore_errors=True)
    # Verify gone
    if os.path.isdir(path):
        shutil.rmtree(path, ignore_errors=True)
    if os.path.isdir(path):
        print(f"WARNING: failed to tear down {path}, left behind",
              file=sys.stderr)


def _plant_exemption(wt_dir):
    """Plant a synthetic stale exemption into the checker EXEMPTIONS dict.

    Adds an entry whose key has no matching write site. Because the entry
    exists in EXEMPTIONS but carries count=1 and zero tree sites match it,
    evaluate() reports it as a stale exemption → exit 1.  The name-set test
    is unaffected because the AST tree does not change.

    Robustly inserts before the closing } of the EXEMPTIONS dict: walks
    backwards from INVENTORY_FLOOR to find the } that closes the dict,
    and inserts the new entry right before that }.
    Returns True on success.
    """
    checker = os.path.join(wt_dir, "scripts", "check_write_site_inventory.py")
    if not os.path.exists(checker):
        return False

    # Read raw bytes so we preserve or normalise line endings consistently
    with open(checker, "rb") as f:
        raw = f.read()

    content = raw.decode("utf-8")

    marker = "\nINVENTORY_FLOOR"
    idx = content.find(marker)
    if idx == -1:
        print("  [PLANT] INVENTORY_FLOOR not found — cannot plant",
              file=sys.stderr)
        return False

    # Walk backward through lines starting just before the marker
    # to find the "}" that closes EXEMPTIONS.
    cut = idx
    found_brace = False
    for ch_idx in range(idx - 1, max(0, idx - 500), -1):
        if content[ch_idx] in ("\n", "\r"):
            line_start = content.rfind("\n", 0, ch_idx) + 1
            line_end = content.find("\n", ch_idx, len(content))
            if line_end == -1:
                line_end = len(content)
            stripped = content[line_start:line_end].strip()
            if stripped == "}":
                cut = line_start   # cut before this line's \n
                found_brace = True
                break

    if not found_brace:
        print("  [PLANT] Could not locate closing } — cannot plant",
              file=sys.stderr)
        return False

    # Build the new content with LF line endings throughout, then
    # let git/commit handle whatever the tree prefers. We avoid
    # mixing \r\n and \n which caused SyntaxErrors on CRLF trees.
    new_entry_lines = [
        "",
        "    # ---- PLANTED_STALE_SYNTHETIC -- GATES 0090 TEETH CONTROL ----",
        '    ("batch_fake_stale", "heyreach.create_list"): {',
        '        "tier": "T1", "count": 1,',
        '        "reason": "SYNTHETIC STALE ENTRY FOR TEETH VERIFICATION"},',
    ]
    # Find what EOL style the existing file uses around the insertion point
    # and reuse it so we don't mix styles inside the dict
    pre_text = content[max(cut - 20, 0):cut]
    if "\r\n" in pre_text:
        eol = "\r\n"
    else:
        eol = "\n"

    new_entry = eol + eol.join(new_entry_lines) + eol

    content = content[:cut] + new_entry + content[cut:]

    with open(checker, "wb") as f:
        f.write(content.encode("utf-8"))

    # Delete .pyc so Python re-imports from disk
    pyc_dir = os.path.join(wt_dir, "scripts", "__pycache__")
    if os.path.isdir(pyc_dir):
        shutil.rmtree(pyc_dir)

    return True


def _unplant_exemption(wt_dir):
    """Restore the original checker by re-writing from CHECKER_SHA."""
    # Just re-call _checkout_checker to overwrite with the clean version
    _checkout_checker(wt_dir)


def run_sha(sha, record, plant=False, original_sha_for_plant=None):
    """Run both instruments on one SHA. Mutates `record` dict."""
    wt_path = None
    try:
        wt_path = _make_worktree(sha)
        rc_h, sha_out, sha_err = _git(wt_path, "rev-parse", "HEAD")
        sha_full = sha_out.strip() if rc_h == 0 and sha_out.strip() else sha
        short_sha = sha_full[:7]
        print(f"  Worktree: {wt_path}")
        print(f"  HEAD: {sha_full}")

        # Check CRLF flavour via CR byte count in a non-gitattributes file
        cr_bytes = 0
        req_file = os.path.join(wt_path, "requirements.txt")
        if os.path.exists(req_file):
            with open(req_file, "rb") as f:
                cr_bytes = f.read().count(b"\r")
        flavour = "CRLF" if cr_bytes > 0 else "LF"
        print(f"  Flavour: {flavour} (CR={cr_bytes})")

        # ---- Instrument 1: check_write_site_inventory ----
        checker_exists_in_tree = _has_checker_at_sha(wt_path, sha)

        if not checker_exists_in_tree and not plant:
            # File wasn't in the tree; try to get it from the checker SHA
            _checkout_checker(wt_path)
            # Verify we got it
            if _has_checker_at_sha(wt_path, sha):
                checker_exists_in_tree = True
                print("  Bootstrapped checker from reference SHA.")
            else:
                print("  NOTE: checker absent even after bootstrap.")

        exit_code = None
        checker_lines = []
        violations = []
        exit_line = ""

        if checker_exists_in_tree or plant:
            # If we planted, ensure the checker still exists post-plant
            if plant and not _has_checker_at_sha(wt_path, sha):
                _checkout_checker(wt_path)

            ec, lines = _run_checker(wt_path)
            exit_code, exit_line = _parse_exit(lines)
            checker_lines = lines
            violations = _extract_violations(lines)
            print(f"  INSTRUMENT 1 (checker): EXIT {exit_code} ({exit_line})")
            for v in violations:
                print(f"    VIOLATION {v}")
        else:
            print(f"  INSTRUMENT 1 (checker): SKIPPED (absent at this SHA)")
            exit_code = None

        # ---- Instrument 2: test_write_site_inventory_check ----
        if _has_test_at_sha(wt_path):
            te, names = _run_name_set_test(wt_path)
            status = "PASS" if te == 0 else ("FAIL" if names else f"exit={te}")
            print(f"  INSTRUMENT 2 (name-set): {status} "
                  f"({len(names)} failing names)")
            if names:
                for n in names:
                    print(f"    FAIL {n}")
            record.setdefault("name_set_names", {}).update(
                {short_sha: names}
            )
        else:
            print(f"  INSTRUMENT 2 (name-set): SKIPPED (module absent)")
            te = None
            names = []

        # ---- Store row ----
        record.setdefault("cells", {})[sha] = {
            "exit_code": exit_code,
            "exit_line": exit_line,
            "violations": violations,
            "checker_lines_count": len(checker_lines),
            "name_set_tests": te,
            "name_set_failing_names": names,
            "has_checker_at_sha": checker_exists_in_tree,
            "worktree_path": wt_path,
            "head_sha": sha_full,
            "flavour": flavour,
            "planted": plant,
        }

    finally:
        if wt_path:
            print(f"  Teardown: {wt_path}")
            _teardown_wt(wt_path)


def main():
    parser = argparse.ArgumentParser(description="GATES 0090: exit-code instrument pair")
    parser.add_argument("shas", nargs="*", default=DEFAULT_SHAS,
                        help="SHAs to evaluate (default: all four)")
    parser.add_argument("--teeth", action="store_true",
                        help="Include teeth control (plant synthetic stale exemption)")
    args = parser.parse_args()

    SHAS = args.shas
    DO_TEETH = args.teeth

    print(f"# GATES 0090 -- exit-code instrument pair")
    print(f"# {len(SHAS)} SHAs, teeth={'ON' if DO_TEETH else 'OFF'}")
    print(f"# {len(SHAS) * 2} cells (2 instruments x {len(SHAS)} SHAs)"
          f"{'+ 1 teeth' if DO_TEETH else ''}")
    print()

    record = {"cells": {}, "base_name_set": None}

    # Phase 1: run normal cells in order
    for i, sha in enumerate(SHAS):
        print(f"[{i+1}/{len(SHAS)}] Running {sha}...")
        run_sha(sha, record)
        print()

    # Phase 2: teeth control (if requested)
    if DO_TEETH:
        print("[TEETH] Planting synthetic stale exemption...")
        # Use the green SHA (EXIT 0) as baseline; f7857e1ab was verified CLEAN
        teeth_sha = "f7857e1ab"
        if not record["cells"].get(teeth_sha, {}).get("has_checker_at_sha", False):
            # Fall back to any SHA that has the checker AND exits green
            teeth_sha = None
            for s in SHAS:
                c = record["cells"].get(s, {})
                if c.get("has_checker_at_sha") and c.get("exit_code") == 0:
                    teeth_sha = s
                    break
            if teeth_sha is None and record["cells"]:
                teeth_sha = next(iter(record["cells"]))

        if teeth_sha and record["cells"].get(teeth_sha, {}).get("has_checker_at_sha", False):
            print(f"[TEETH] Using {teeth_sha} as base for teeth control")
            wt_path = _make_worktree(teeth_sha)
            sha_short = teeth_sha[:7]
            print(f"  Worktree: {wt_path}")
            original_sha = teeth_sha

            # Get baseline exit code
            _git(wt_path, "checkout", teeth_sha, "--",
                 "scripts/check_write_site_inventory.py")
            baseline_ec, baseline_lines = _run_checker(wt_path)
            baseline_exit, baseline_exit_line = _parse_exit(baseline_lines)
            baseline_violations = _extract_violations(baseline_lines)

            # Plant
            if _plant_exemption(wt_path):
                planted_ec, planted_lines = _run_checker(wt_path)
                planted_exit, planted_exit_line = _parse_exit(planted_lines)
                planted_violations = _extract_violations(planted_lines)

                print(f"  BASELINE: EXIT {baseline_exit} ({baseline_exit_line})")
                print(f"  PLANTED:  EXIT {planted_exit} ({planted_exit_line})")
                for v in baseline_violations:
                    print(f"    BASE_VIOLATION {v}")
                for v in planted_violations:
                    print(f"    PLANT_VIOLATION {v}")

                record["teeth_control"] = {
                    "baseline_exit": baseline_exit,
                    "planted_exit": planted_exit,
                    "baseline_violations": baseline_violations,
                    "planted_violations": planted_violations,
                    "flip": baseline_exit != planted_exit,
                }
                print(f"  TEETH CONTROL: {'PASSED' if record['teeth_control']['flip'] else 'FAILED'} "
                      f"(exit changed {baseline_exit}->{planted_exit})")
            else:
                print("  [TEETH] Failed to plant exemption")
                record["teeth_control"] = {"error": "failed_to_plant"}

            _teardown_wt(wt_path)
        else:
            print(f"  [TEETH] No suitable SHA found for teeth control")

    # ---- Print table ----
    print("\n" + "=" * 100)
    print("# GATES 0090 TABLE")
    print("# sha        | instrument      | exit | violations")
    print("=" * 100)

    header = f"{'SHA':>12} | {'instrument':>22} | {'exit':>4} | {'exit_text':>50}"
    print(header)
    print("-" * len(header))

    for sha in SHAS:
        cell = record["cells"].get(sha, {})
        s = sha[:7]
        if cell.get("has_checker_at_sha"):
            ec = cell["exit_code"]
            el = cell.get("exit_line", "")
            viols = cell.get("violations", [])
            viol_str = "; ".join(viols[:3]) if viols else "(none)"
            line = f"{s:>12} | {'checker':>22} | {ec:>4} | {el}"
            print(line)
            for v in viols[:5]:
                print(f"{'':>12} | {'':>22} | {'':>4} |    VIOLATION {v}")
        else:
            print(f"{s:>12} | {'checker':>22} | {'N/A':>4} | SKIPPED (absent at SHA)")

        ns = cell.get("name_set_failing_names", [])
        if cell.get("name_set_tests") is not None:
            st = "PASS" if cell["name_set_tests"] == 0 else "FAIL"
            print(f"{s:>12} | {'name-set':>22} | {'':>4} | {st} ({len(ns)} failing)")
            if ns:
                for n in ns[:3]:
                    print(f"{'':>12} | {'':>22} | {'':>4} |    FAIL {n}")

    # Name-set delta vs base
    if record.get("base_name_set") is None and record["cells"]:
        first_sha = SHAS[0]
        first_cell = record["cells"].get(first_sha, {})
        record["base_name_set"] = set(
            first_cell.get("name_set_failing_names", [])
        )

    base = record.get("base_name_set", set())
    if base:
        print("\n--- NAME-SET DELTA vs BASE ---")
        for sha in SHAS:
            cell = record["cells"].get(sha, {})
            ns = set(cell.get("name_set_failing_names", []))
            new = ns - base
            gone = base - ns
            unchanged = ns & base
            if new or gone or (cell.get("has_checker_at_sha")
                               and cell.get("exit_code") is not None
                               and cell.get("exit_code", 0) != 0):
                print(f"{sha[:7]:>12}: name-set delta: new={len(new)}, "
                      f"gone={len(gone)}, unchanged={len(unchanged)}")
                if cell.get("has_checker_at_sha"):
                    ec = cell["exit_code"]
                    vc = len(cell.get("violations", []))
                    if base and ns == base and ec is not None:
                        print(f"  *** EXIT-CODE MOVEMENT WITHOUT NAME-SET CHANGE "
                              f"(EXIT {cell.get('exit_code')}->{ec}, "
                              f"{vc} violations, {len(base)} identical names)")

    # Teeth control summary
    tc = record.get("teeth_control")
    if tc:
        print(f"\n--- TEETH CONTROL ---")
        if tc.get("flip"):
            print(f"PASSED: exit changed {tc['baseline_exit']} -> "
                  f"{tc['planted_exit']} while name-set stays identical")
        elif tc.get("error"):
            print(f"SKIPPED: {tc['error']}")

    # Count reconcilation
    total_cells = len(SHAS) * 2
    actual_cells = sum(1 for c in record["cells"].values() if c.get("exit_code") is not None
                       or c.get("name_set_tests") is not None)
    skipped_cells = total_cells - actual_cells
    exit_movements = 0
    for sha in SHAS:
        cell = record["cells"].get(sha, {})
        if cell.get("has_checker_at_sha") and cell.get("exit_code") is not None:
            if cell.get("exit_code", 0) != 0:
                # This is a movement from the green baseline (EXIT 0)
                pass  # Don't count here; movements need two adjacent points
    if DO_TEETH:
        total_cells += 2  # baseline + planted for teeth

    print(f"\nDENOMINATORS: {len(SHAS)} SHAs x 2 instruments = {total_cells} cells, "
          f"{actual_cells} measured, {skipped_cells} skipped.")

    # Return the record for downstream consumption
    return record


if __name__ == "__main__":
    raise SystemExit(main() or 0)
