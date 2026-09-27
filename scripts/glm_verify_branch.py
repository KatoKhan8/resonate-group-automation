#!/usr/bin/env python3
"""GLM first-pass verification of a finished worker branch.

    py -3 scripts/glm_verify_branch.py --branch qwen-worker-2-r59 --task TASK-323
    py -3 scripts/glm_verify_branch.py --branch qwen-worker-2-r59 --task TASK-323 --dry-run

READ-ONLY apart from the report it writes. No merge, no cherry-pick, no push,
no task-file move. Claude integrates; this tool reports a verdict.

WHY GLM AND NOT A SECOND MODEL. GLM-5.3 already reviews code in
`scripts/glm_review.py` and has found real defects the authoring session
missed. Reusing the same adapter, the same prompt discipline and the same
token budget means one credential, one price list, one failure mode.

WHAT THIS CHECKS THAT exit=0 DOES NOT. Three defects shipped on 2026-09-26
that a green test run did not catch: a bridge function with no caller, a tool
reporting 56 DISCONNECTED modules of which most were in use, and four scratch
files committed to the repo root. This script asks GLM the three questions
that catch those, runs the branch's own acceptance commands, and diffs the
failing-test set against a known baseline.
"""
import argparse
import datetime
import glob
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.providers import glm, load_env                          # noqa: E402

DEFAULT_MAX_TOKENS = 16000
SYSTEM = (
    "You are an adversarial reviewer of a production cold-outreach system. "
    "You are looking for DEFEATS and MEASURABLE COSTS, not style. A finding "
    "must name a concrete input, call order, state, or arithmetic consequence "
    "at a stated scale. If you cannot construct one, say NO FINDING - that "
    "answer is worth more than a plausible-sounding guess. Be brief."
)

BASELINE_PATH = os.path.join(ROOT, "docs", "state",
                             "SUITE-BASELINE-2026-09-26.txt")

SCRATCH_PATTERN = re.compile(r"^[^/\\]+\.(txt|err|out|log)$")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--branch", required=True,
                        help="Worker branch to verify, e.g. qwen-worker-2-r59")
    parser.add_argument("--task", required=True,
                        help="Task id, e.g. TASK-323")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the prompt and call nothing")
    parser.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS)
    parser.add_argument("--timeout", type=int, default=180)
    return parser.parse_args(argv)


# --------------------------------------------------------------- git helpers


def _git(*args, cwd=None):
    """Run a git command, return CompletedProcess."""
    return subprocess.run(
        ["git"] + list(args),
        capture_output=True, text=True,
        cwd=cwd or ROOT, timeout=120)


def _branch_exists(branch):
    return _git("rev-parse", "--verify", branch).returncode == 0


def _diff_against_master(branch):
    merge_base = _git("merge-base", "master", branch)
    if merge_base.returncode != 0:
        return None, None
    base = merge_base.stdout.strip()
    stat = _git("diff", "--stat", base, branch)
    diff = _git("diff", base, branch)
    return (stat.stdout if stat.returncode == 0 else None,
            diff.stdout if diff.returncode == 0 else None)


def _changed_files(branch):
    merge_base = _git("merge-base", "master", branch)
    if merge_base.returncode != 0:
        return []
    base = merge_base.stdout.strip()
    r = _git("diff", "--name-only", base, branch)
    if r.returncode != 0:
        return []
    return [f for f in r.stdout.strip().splitlines() if f]


def _new_test_files(branch):
    merge_base = _git("merge-base", "master", branch)
    if merge_base.returncode != 0:
        return []
    base = merge_base.stdout.strip()
    r = _git("diff", "--diff-filter=A", "--name-only", base, branch, "--",
             "tests/")
    if r.returncode != 0:
        return []
    return [f for f in r.stdout.strip().splitlines() if f]


def _changed_test_files(branch):
    """All test files added OR modified on the branch."""
    merge_base = _git("merge-base", "master", branch)
    if merge_base.returncode != 0:
        return []
    base = merge_base.stdout.strip()
    r = _git("diff", "--name-only", base, branch, "--", "tests/")
    if r.returncode != 0:
        return []
    return [f for f in r.stdout.strip().splitlines()
            if f and f.endswith(".py")]


# --------------------------------------------------------------- worktree


def _create_worktree(branch, suffix=""):
    """Create a temporary worktree for the branch. Returns path."""
    wt_base = os.path.join(ROOT, ".qwen", "worktrees")
    os.makedirs(wt_base, exist_ok=True)
    wt_name = f"verify-{os.getpid()}{suffix}"
    wt_path = os.path.join(wt_base, wt_name)
    # Clean up any stale worktree at this path
    if os.path.exists(wt_path):
        _git("worktree", "remove", "--force", wt_path)
    r = _git("worktree", "add", "--detach", wt_path, branch)
    if r.returncode != 0:
        raise RuntimeError(f"git worktree add failed: {r.stderr}")
    return wt_path


def _remove_worktree(wt_path):
    """Remove a temporary worktree."""
    try:
        _git("worktree", "remove", "--force", wt_path)
    except Exception:
        if os.path.exists(wt_path):
            shutil.rmtree(wt_path, ignore_errors=True)


# --------------------------------------------------------------- task parsing


def _find_task_file(task_id):
    dirs = ["TODO", "RUNNING", "REVIEW", "REWORK", "DONE",
            "BLOCKED", "BLOCKED_QUOTA"]
    for d in dirs:
        pattern = os.path.join(ROOT, "docs", "qwen-tasks", d,
                               f"{task_id}-*.md")
        matches = glob.glob(pattern)
        if matches:
            return matches[0]
    return None


def _extract_acceptance_commands(task_file):
    """Extract shell commands from the Acceptance section of a task file.

    Handles multi-line commands with backslash continuations.
    """
    if not task_file or not os.path.exists(task_file):
        return []
    text = open(task_file, encoding="utf-8").read()

    in_acceptance = False
    commands = []
    current_cmd = None

    for line in text.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("## acceptance"):
            in_acceptance = True
            continue
        if in_acceptance and stripped.startswith("## "):
            break
        if not in_acceptance:
            continue

        if current_cmd is not None:
            if stripped.endswith("\\"):
                current_cmd += " " + stripped[:-1].strip()
            else:
                current_cmd += " " + stripped
                commands.append(current_cmd)
                current_cmd = None
            continue

        if stripped.startswith(("py -3", "python ", "grep ", "scripts/")):
            if stripped.endswith("\\"):
                current_cmd = stripped[:-1].strip()
            else:
                commands.append(stripped)

    if current_cmd is not None:
        commands.append(current_cmd)

    return commands


# --------------------------------------------------------------- baseline


def _load_baseline():
    if not os.path.exists(BASELINE_PATH):
        return set()
    names = set()
    for line in open(BASELINE_PATH, encoding="utf-8"):
        line = line.strip()
        if line.startswith(("FAIL ", "ERROR ")):
            parts = line.split(None, 1)
            if len(parts) == 2:
                names.add(parts[1])
    return names


# --------------------------------------------------------------- test runner


def _run_tests_in_worktree(branch, test_files):
    """Check out the branch in a temp worktree, run the tests, return results.

    Returns (failing_names: set, output: str, error: str|None).
    """
    if not test_files:
        return set(), "(no test files to run)", None

    modules = []
    for f in test_files:
        if f.endswith(".py") and f.startswith("tests/"):
            # tests/foo/bar.py -> tests.foo.bar
            mod = f.replace("/", ".").replace("\\", ".")[:-3]
            modules.append(mod)
    if not modules:
        return set(), "(no test modules resolved)", None

    wt_path = None
    try:
        wt_path = _create_worktree(branch, suffix="-tests")
        args = [sys.executable, "-m", "unittest"] + modules + ["-v"]
        try:
            result = subprocess.run(
                args, capture_output=True, text=True,
                cwd=wt_path, timeout=600)
            output = result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            return set(), "", "TIMEOUT after 600s"

        failing = set()
        for line in output.splitlines():
            line = line.strip()
            if line.startswith(("FAIL: ", "ERROR: ")):
                parts = line.split(None, 1)
                if len(parts) == 2:
                    failing.add(parts[1])
        return failing, output, None
    except Exception as e:
        return set(), "", f"{type(e).__name__}: {e}"
    finally:
        if wt_path:
            _remove_worktree(wt_path)


def _run_acceptance_in_worktree(branch, commands):
    """Run acceptance commands in a temp worktree on the branch."""
    if not commands:
        return "(no acceptance commands extracted from task file)"

    wt_path = None
    try:
        wt_path = _create_worktree(branch, suffix="-accept")
        results = []
        for cmd in commands:
            try:
                r = subprocess.run(
                    cmd, shell=True, capture_output=True, text=True,
                    cwd=wt_path, timeout=120,
                    env={**os.environ, "PYTHONPATH": wt_path})
                out = r.stdout + r.stderr
                results.append(f"$ {cmd}\nexit={r.returncode}\n{out.strip()}")
            except subprocess.TimeoutExpired:
                results.append(f"$ {cmd}\nTIMEOUT after 120s")
            except Exception as e:
                results.append(f"$ {cmd}\n{type(e).__name__}: {e}")
        return "\n\n".join(results)
    except Exception as e:
        return f"(worktree failed: {type(e).__name__}: {e})"
    finally:
        if wt_path:
            _remove_worktree(wt_path)


# --------------------------------------------------------------- scratch check


def _check_scratch_files(changed_files):
    scratch = []
    for f in changed_files:
        if SCRATCH_PATTERN.match(f):
            scratch.append(f)
    return scratch


# --------------------------------------------------------------- GLM prompt


VERIFY_PROMPT = """You are verifying a worker branch in a production
cold-outreach system. The branch claims to have completed a task. Your job
is to check three things that exit=0 does not catch.

## The branch

Branch: {branch}
Task: {task}
Changed files:
{changed_files}

## The diff (summary)

{diff_stat}

## The task's acceptance commands produced this output:

{acceptance_output}

## The test results (new/changed tests on this branch):

{test_output}

## Three questions. Answer each one.

**1. Does the new code have a production caller?** Not a test, not `work/`,
not a re-export nobody calls. If the branch adds a function to bridge two
modules, does anything call the BRIDGE? Name the caller or say NO CALLER.

**2. Can the acceptance check fail?** Given the change, name an input that
makes it fail. If you cannot name one, the check is vacuous.

**3. Does any number in the result block reconcile?** A count, a cost, a row
total. If the branch claims a measurement, can you recompute it from the
diff?

## Also check

- Does every changed file answer to the task? Name any file that does not.
- Are there scratch files (*.txt, *.err, *.out at the repo root)?

## Verdict

End your answer with exactly one of:
- VERDICT: PASS
- VERDICT: FAIL - <one-line reason>
- VERDICT: NEEDS_CLAUDE - <one-line reason>

Be concrete. Cite file names and line numbers from the diff.
"""


def _build_prompt(branch, task, changed_files, diff_stat,
                  acceptance_output, test_output):
    return VERIFY_PROMPT.format(
        branch=branch,
        task=task,
        changed_files="\n".join(f"- {f}" for f in changed_files) or "(none)",
        diff_stat=diff_stat or "(could not generate)",
        acceptance_output=acceptance_output or "(no commands extracted)",
        test_output=test_output or "(no new tests or could not run)",
    )


# --------------------------------------------------------------- verdict


def _parse_verdict(content):
    for line in content.splitlines():
        stripped = line.strip().upper()
        if stripped.startswith("VERDICT:"):
            rest = line.strip()[len("VERDICT:"):].strip()
            if rest.startswith("PASS"):
                return "PASS", rest[len("PASS"):].strip().lstrip("- ").strip()
            elif rest.startswith("FAIL"):
                return "FAIL", rest[len("FAIL"):].strip().lstrip("- ").strip()
            elif rest.startswith("NEEDS_CLAUDE"):
                return "NEEDS_CLAUDE", rest[len("NEEDS_CLAUDE"):].strip().lstrip("- ").strip()
    return "NEEDS_CLAUDE", "GLM did not emit a VERDICT line"


# --------------------------------------------------------------- spend


def _read_spend():
    """Read total GLM model spend from the ledger."""
    try:
        from src import spendledger
        rows = spendledger.load()
        model_rows = [r for r in rows if r.get("client") == "_model"
                      and r.get("provider") == "glm"]
        return len(model_rows), sum(r.get("expected_cost", 0)
                                    for r in model_rows)
    except Exception:
        return 0, 0


# --------------------------------------------------------------- main


def main(argv=None):
    args = parse_args(argv)

    if not _branch_exists(args.branch):
        print(f"ERROR: branch {args.branch!r} does not exist")
        return 2

    task_file = _find_task_file(args.task)
    if not task_file:
        print(f"ERROR: task file for {args.task} not found")
        return 2

    print(f"Verifying branch {args.branch} for {args.task}")
    print(f"Task file: {task_file}")

    # Step 1: Extract and run acceptance commands in a worktree
    print("\n--- Step 1: Acceptance commands ---")
    commands = _extract_acceptance_commands(task_file)
    print(f"Extracted {len(commands)} acceptance commands")
    acceptance_output = _run_acceptance_in_worktree(args.branch, commands)
    print(acceptance_output.encode("ascii", "replace").decode("ascii")[:2000])

    # Step 2: Diff analysis
    print("\n--- Step 2: Diff analysis ---")
    changed_files = _changed_files(args.branch)
    diff_stat, diff_full = _diff_against_master(args.branch)
    print(f"Changed files: {len(changed_files)}")
    for f in changed_files:
        print(f"  {f}")

    scratch = _check_scratch_files(changed_files)
    if scratch:
        print(f"\nHARD FAIL: scratch files at repo root: {scratch}")

    # Step 3: Test analysis - run in worktree
    print("\n--- Step 3: Test analysis ---")
    test_files = _changed_test_files(args.branch)
    print(f"Changed test files: {len(test_files)}")
    for t in test_files:
        print(f"  {t}")

    failing_names, test_output, test_error = _run_tests_in_worktree(
        args.branch, test_files)
    if test_error:
        print(f"Test error: {test_error}")
    baseline = _load_baseline()
    new_failures = failing_names - baseline
    print(f"Failing tests: {len(failing_names)} total, "
          f"{len(new_failures)} new (not in baseline)")
    if new_failures:
        for n in sorted(new_failures):
            print(f"  NEW: {n}")

    # Build the GLM prompt
    prompt = _build_prompt(
        args.branch, args.task, changed_files,
        diff_stat, acceptance_output,
        test_output[:8000] if test_output else "")

    if args.dry_run:
        print(f"\n--- DRY RUN ---")
        print(f"Prompt length: {len(prompt)} chars")
        if scratch:
            print(f"\nHARD FAIL would fire: scratch files {scratch}")
        if new_failures:
            print(f"\nNew test failures would fire FAIL: {new_failures}")
        print("\nDRY RUN: GLM was not called.")
        return 0

    # Step 4: Call GLM
    print("\n--- Step 4: GLM verification ---")
    load_env(os.path.join(ROOT, "config", ".env"))

    n_before, cost_before = _read_spend()

    try:
        result = glm.complete(
            prompt, system=SYSTEM,
            max_tokens=args.max_tokens, timeout=args.timeout)
    except Exception as exc:
        print(f"GLM call failed: {type(exc).__name__}: {exc}")
        verdict = "NEEDS_CLAUDE"
        reason = f"GLM call failed: {type(exc).__name__}"
        content = f"GLM call failed: {exc}"
        result = None
    else:
        print(f"  {result['model']} {result['seconds']}s {result['usage']}")
        content = result["content"]
        print(content.encode("ascii", "replace").decode("ascii")[:3000])
        verdict, reason = _parse_verdict(content)

    n_after, cost_after = _read_spend()
    spend_delta_rows = n_after - n_before
    spend_delta_cost = cost_after - cost_before

    # Override verdict on deterministic failures
    if scratch:
        verdict = "FAIL"
        reason = f"scratch files committed: {scratch}"
    if new_failures:
        verdict = "FAIL"
        reason = (f"{len(new_failures)} new test failures not in baseline: "
                  f"{sorted(new_failures)[:5]}")

    # Write report
    stamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    out_dir = os.path.join(ROOT, "docs", "glm-reviews")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"branch-{args.task}.md")

    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(f"# GLM branch verification: {args.task}\n\n")
        fh.write(f"Branch: `{args.branch}`\n")
        fh.write(f"Date: {stamp}\n")
        fh.write(f"Model: {result['model'] if result else 'N/A'}\n")
        fh.write(f"Duration: {result['seconds'] if result else 'N/A'}s\n")
        fh.write(f"Usage: {result['usage'] if result else 'N/A'}\n\n")
        fh.write(f"## Verdict: {verdict}\n\n")
        if reason:
            fh.write(f"**{reason}**\n\n")
        fh.write(f"## GLM spend\n\n")
        fh.write(f"This call: {spend_delta_rows} ledger rows, "
                 f"{spend_delta_cost} micro-USD\n\n")
        if scratch:
            fh.write(f"## Scratch files (HARD FAIL)\n\n")
            for s in scratch:
                fh.write(f"- `{s}`\n")
            fh.write("\n")
        if new_failures:
            fh.write(f"## New test failures\n\n")
            for n in sorted(new_failures):
                fh.write(f"- `{n}`\n")
            fh.write("\n")
        fh.write(f"## Changed files ({len(changed_files)})\n\n")
        for f in changed_files:
            fh.write(f"- `{f}`\n")
        fh.write("\n")
        fh.write(f"## Diff stat\n\n```\n{diff_stat or 'N/A'}\n```\n\n")
        fh.write(f"## Acceptance output\n\n```\n{acceptance_output}\n```\n\n")
        fh.write(f"## GLM response\n\n{content}\n")

    print(f"\n--- Verdict: {verdict} ---")
    if reason:
        print(reason.encode("ascii", "replace").decode("ascii"))
    print(f"\nSpend: {spend_delta_rows} rows, {spend_delta_cost} micro-USD")
    print(f"Report written to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
