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
import json
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
                             "SUITE-BASELINE-2026-10-02-FULL.json")

SCRATCH_PATTERN = re.compile(r"^[^/\\]+\.(txt|err|out|log)$")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--branch", required=True,
                        help="Worker branch to verify, e.g. qwen-worker-2-r59")
    parser.add_argument("--task", required=True,
                        help="Task id, e.g. TASK-323")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the prompt and call nothing")
    # `DEFAULT_MAX_TOKENS` above, NOT a second copy of the number. I briefly
    # wrote the literal here and that was two authorities for one figure, which
    # is the defect this file exists to catch in other people's branches.
    #
    # The figure itself is load-bearing and must not be lowered: this model
    # spends most of its output budget on REASONING tokens, so a small cap
    # returns an EMPTY answer, `_parse_verdict` reads nothing as NEEDS_CLAUDE,
    # and the verifier abstains forever while looking like it ran. The adapter's
    # own default is 1024; this script has always overridden it, and an earlier
    # claim of mine that the 1024 was in force here was wrong - measured by
    # reading `DEFAULT_MAX_TOKENS` on master, where it is already 16000.
    parser.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS)
    parser.add_argument("--ledger-client", default=None,
                        help="Who this call is billed to. Defaults to the "
                             "task id, because model spend must be "
                             "attributed to a client or a task and never "
                             "left unattributed.")
    parser.add_argument("--timeout", type=int, default=180)
    return parser.parse_args(argv)


# --------------------------------------------------------------- git helpers


def _git(*args, cwd=None):
    """Run a git command, return CompletedProcess."""
    return subprocess.run(
        ["git"] + list(args),
        capture_output=True, text=True,
        cwd=cwd or ROOT, timeout=120)


def env_path():
    """The ONE `config/.env`, the main checkout's, from any worktree.

    MEASURED 2026-10-02 and this is why GLM verification never ran today:
    `config/.env` is gitignored, so a worktree created by `git worktree add` has
    NONE, and `load_env(ROOT/config/.env)` from a worktree found nothing. The
    call then failed with `MissingKey: no ZAI_API_KEY in config/.env` and the
    verdict became NEEDS_CLAUDE - a verifier that abstains for an environmental
    reason, reported as if it had considered the code.

    Same shape as the suite lock, same fix: `--path-format=absolute
    --git-common-dir` is the one path identical from the main checkout and from
    every worktree. A relative answer is refused rather than resolved, because
    `abspath` would resolve it against this worktree and put us back where we
    started.
    """
    out = _git("rev-parse", "--path-format=absolute", "--git-common-dir")
    value = (out.stdout or "").strip() if out.returncode == 0 else ""
    if value and os.path.isabs(value):
        candidate = os.path.join(os.path.dirname(os.path.abspath(value)),
                                 "config", ".env")
        if os.path.isfile(candidate):
            return candidate
    return os.path.join(ROOT, "config", ".env")


def _branch_exists(branch):
    return _git("rev-parse", "--verify", branch).returncode == 0


def _merge_commit_for(branch):
    """The merge that brought this branch into master, or None.

    MEASURED 2026-10-02 on `task-step-objectives-convergence`: a branch that is
    ALREADY MERGED has an empty diff against master, because the merge base is
    its own tip. `--dry-run` reported "Changed files: 0" and the prompt carried
    no code at all - so a retroactive verification of a merged branch would have
    asked GLM to review nothing and any PASS it returned would be vacuous.

    For a merged branch the honest review unit is what the merge ADDED to master,
    which is `M^1..M`. `--ancestry-path` keeps only merges on the path from the
    branch to master, and the LAST of those, listed oldest last, is the one that
    brought it in.
    """
    if _git("merge-base", "--is-ancestor", branch, "master").returncode != 0:
        return None
    out = _git("rev-list", "--ancestry-path", "--merges", f"{branch}..master")
    if out.returncode != 0:
        return None
    commits = [c for c in out.stdout.split() if c]
    return commits[-1] if commits else None


def review_range(branch):
    """`(base, head, how)` - the two commits this verification compares.

    `how` names which case it is, because a reader of the report must be able to
    tell "reviewed the branch against where it forked" from "reviewed what its
    merge added to master", and from "found nothing to review", which is never a
    pass.
    """
    merged = _merge_commit_for(branch)
    if merged:
        return merged + "^1", merged, f"merged by {merged[:8]}"
    merge_base = _git("merge-base", "master", branch)
    if merge_base.returncode != 0:
        return None, None, "no merge base with master"
    base = merge_base.stdout.strip()
    if base == _git("rev-parse", branch).stdout.strip():
        return None, None, ("already contained in master with no merge commit "
                            "(fast-forward); nothing to review here")
    return base, branch, "unmerged branch against its fork point"


def _diff_against_master(branch):
    base, head, _how = review_range(branch)
    if not base:
        return None, None
    stat = _git("diff", "--stat", base, head)
    diff = _git("diff", base, head)
    return (stat.stdout if stat.returncode == 0 else None,
            diff.stdout if diff.returncode == 0 else None)


def _changed_files(branch):
    base, head, _how = review_range(branch)
    if not base:
        return []
    r = _git("diff", "--name-only", base, head)
    if r.returncode != 0:
        return []
    return [f for f in r.stdout.strip().splitlines() if f]


def _new_test_files(branch):
    base, head, _how = review_range(branch)
    if not base:
        return []
    r = _git("diff", "--diff-filter=A", "--name-only", base, head, "--",
             "tests/")
    if r.returncode != 0:
        return []
    return [f for f in r.stdout.strip().splitlines() if f]


def _changed_test_files(branch):
    """All test files added OR modified on the branch."""
    base, head, _how = review_range(branch)
    if not base:
        return []
    r = _git("diff", "--name-only", base, head, "--", "tests/")
    if r.returncode != 0:
        return []
    return [f for f in r.stdout.strip().splitlines()
            if f and f.endswith(".py")]


# --------------------------------------------------------------- worktree


def _create_worktree(branch, suffix=""):
    """Create a temporary worktree for the branch. Returns path."""
    # A SHORT base, because Windows MAX_PATH is 260 and this repository has a
    # 104-character tracked path. MEASURED 2026-10-02: the old base under
    # `ROOT/.qwen/worktrees/verify-<pid>/` produced a 256-character path for
    # `docs/qwen-tasks/REVIEW/TASK-205-...md` and `git worktree add` failed with
    # "Filename too long", then "Could not reset index file to revision HEAD".
    # The run carried on and printed "Failing tests: 0 total, 0 new" - a zero
    # from a checkout that never happened. The same path under the system temp
    # directory is 149 characters.
    wt_base = tempfile.gettempdir()
    os.makedirs(wt_base, exist_ok=True)
    wt_name = f"v{os.getpid()}{suffix}"
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
#
# THE TWO SIDES OF THIS DIFF ARE SHAPED DIFFERENTLY AND USED NOT TO BE
# RECONCILED, WHICH MADE EVERY VERDICT THIS SCRIPT PRODUCED A FAIL.
#
# `unittest -v` writes           FAIL: test_x (tests.mod.Class.test_x)
# the baseline file holds        FAIL tests.mod.Class.test_x  ->  mod.Class.test_x
#
# The old code stored `parts[1]` verbatim, i.e. the whole
# "test_x (tests.mod.Class.test_x)" string, and subtracted the baseline's bare
# dotted names from it. The two sets could never intersect, so EVERY failing
# test came back as "new (not in baseline)" and the verdict was always FAIL -
# including for branches whose failures were entirely baseline names. Measured
# on 2026-09-28: the TASK-364 run reported two "new" failures, and both are on
# lines 62 and 63 of the baseline file; the TASK-400 run reported seventeen, and
# every one sampled was in the baseline too.
#
# That is worse than a broken check, because the operator's merge rule is "a
# valid GLM PASS means merge". A verifier that cannot emit PASS does not slow
# merges down - it teaches everybody to ignore the verifier, which is how a real
# finding gets waved through later.


def acceptance_text(task_file):
    """The task's Acceptance section verbatim, or "".

    MEASURED 2026-10-02: only 108 of 581 task files carry an `## Acceptance`
    heading at all, and of those many state PROSE criteria rather than shell
    commands - TASK-903 has one heading and four prose items, which is why the
    command extractor correctly returned zero. The extractor is not broken; the
    premise that acceptance is runnable is false for most of this repository.

    So the acceptance is SHOWN even when it cannot be executed. An adversarial
    reviewer asked "can the acceptance check fail?" needs to know what the task
    claimed; without this it was being asked about a check it had never seen.
    """
    if not task_file or not os.path.exists(task_file):
        return ""
    out, inside = [], False
    for line in open(task_file, encoding="utf-8").read().splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("## acceptance"):
            inside = True
            continue
        if inside and stripped.startswith("## "):
            break
        if inside:
            out.append(line)
    return "\n".join(out).strip()


def normalise_test_name(raw):
    """A failing-test name in the BASELINE's shape, or None.

    Accepts either side's spelling so the comparison is symmetric:
    "test_x (tests.mod.Class.test_x)", "tests.mod.Class.test_x" and
    "mod.Class.test_x" all reduce to "mod.Class.test_x". The leading `tests.`
    is dropped because the baseline does not carry it, and a trailing
    parenthesised subtest description is dropped because it is prose.
    """
    if not raw:
        return None
    name = raw.strip()
    # Prefer the parenthesised dotted path that unittest -v appends.
    start = name.find("(")
    if start != -1:
        inner = name[start + 1:]
        end = inner.rfind(")")
        if end != -1:
            inner = inner[:end]
        inner = inner.strip()
        # A subtest line reads "test_x (mod.Class.test_x) [i=1]"; keep the path.
        if inner and " " not in inner:
            name = inner
        elif inner:
            name = inner.split()[0]
    if name.startswith("tests."):
        name = name[len("tests."):]
    return name or None


def _load_baseline():
    if not os.path.exists(BASELINE_PATH):
        return set()
    names = set()
    if BASELINE_PATH.endswith(".json"):
        # `with`, not a bare open(): this leaked a handle on every call and
        # raised a ResourceWarning. On Windows an unclosed handle can fail a
        # later reopen or unlink of the same path, which is one of the ways a
        # test that passes alone fails in company - see TASK-449, where three
        # order-dependent failures are being traced to exactly this class of
        # leak.
        with open(BASELINE_PATH, encoding="utf-8") as fh:
            data = json.load(fh)
        for entry in data.get("entries", []):
            test_name = entry.get("test", "")
            name = normalise_test_name(test_name)
            if name:
                names.add(name)
    else:
        with open(BASELINE_PATH, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line.startswith(("FAIL ", "ERROR ")):
                    parts = line.split(None, 1)
                    if len(parts) == 2:
                        # Normalise this side too, so the comparison is
                        # symmetric and a future change to either spelling
                        # cannot desync them.
                        name = normalise_test_name(parts[1])
                        if name:
                            names.add(name)
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
                    name = normalise_test_name(parts[1])
                    if name:
                        failing.add(name)
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

## The diff

File-level summary, for orientation only:

{diff_stat}

The actual patch follows. **Review the CODE. The summary above cannot answer any
of the three questions below.**

```diff
{diff}
```

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


#: Headroom left under the adapter's bound for the banner and for the fact that
#: the system turn counts against the same budget.
PROMPT_MARGIN = 2_000

#: Room kept for the truncation banner, so the number it states is the
#: number of patch characters actually shown.
BANNER_RESERVE = 400


def _build_prompt(branch, task, changed_files, diff_stat, diff,
                  acceptance_output, test_output):
    """The prompt, with the REAL patch in it and any truncation declared.

    MEASURED 2026-10-02. `_diff_against_master` already returned the full diff
    and `main` threw it away: the prompt's slot was literally named `diff_stat`
    and its heading said "(summary)". So GLM was asked "does the new code have a
    production caller" while being shown file names and line counts. Every
    verdict it produced was formed without ever seeing the code, which is worse
    than no verification, because it reads as verification.

    The patch is BOUNDED and the bound is DECLARED. `glm.complete` refuses a
    prompt over `MAX_PROMPT_CHARS` (60,000) rather than truncating it - the
    adapter's own docstring says a silently shortened prompt produces a confident
    answer to a question that was never asked. So this function fits the patch to
    the room that is actually left, and when it does not fit it says so with exact
    numbers and tells the model that NEEDS_CLAUDE is the correct answer if the
    unseen part could change its verdict. A truncation nobody is told about is
    the same defect as the diffstat, one layer down.
    """
    def render(patch):
        return VERIFY_PROMPT.format(
            branch=branch,
            task=task,
            changed_files="\n".join(f"- {f}" for f in changed_files) or "(none)",
            diff_stat=diff_stat or "(could not generate)",
            diff=patch,
            acceptance_output=acceptance_output or "(no commands extracted)",
            test_output=test_output or "(no new tests or could not run)",
        )

    patch = diff or "(could not generate a diff - answer NEEDS_CLAUDE)"
    room = glm.MAX_PROMPT_CHARS - len(render("")) - len(SYSTEM) - PROMPT_MARGIN
    if room <= 0:
        return render("(the rest of the prompt already fills the budget, so no "
                      "patch could be shown - answer NEEDS_CLAUDE)")
    if len(patch) > room:
        # THE NUMBER MUST BE THE NUMBER. Found by GLM reviewing this very file:
        # the banner used to claim `room` characters were shown while the excerpt
        # was `room - len(banner)` long, overstating the visible patch by its own
        # length. A reviewer deciding whether the unseen part matters was being
        # given a figure that was wrong by about 180 characters - small, and
        # exactly the kind of number this tool exists to catch in other people's
        # work. The shown length is reserved first and then stated.
        shown = max(0, room - BANNER_RESERVE)
        banner = (f"TRUNCATED PATCH: you are seeing the first {shown} characters "
                  f"of {len(patch)}. The remaining {len(patch) - shown} are NOT "
                  f"shown. If what you cannot see could change your verdict, the "
                  f"correct verdict is NEEDS_CLAUDE.\n\n")
        patch = banner + patch[:shown]
    return render(patch)


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
    """GLM spend from the ledger, by CLIENT, and never filtered to one tenant.

    MEASURED 2026-10-02: this filtered `client == "_model"`, a tenant TASK-346
    RETIRED. `glm.complete` defaults an unattributed call to `"unattributed"`
    now, and an attributed one to whatever `ledger_client` names - so the old
    filter matched nothing ever written and the verifier printed "Spend: 0 rows"
    after every call it made. A spend audit that reports clean because it watched
    nothing is worse than none: CLAUDE.md says so about this exact ledger.

    Returns `(rows, cost, by_client)`. The breakdown is returned rather than a
    single total because the standing rule is that model spend must be ATTRIBUTED
    to a client or a task, and a bare total cannot show whether it was. Any
    exception is re-raised as a named failure rather than swallowed into `0, 0`,
    which is the same blindness in a different costume.
    """
    from src import spendledger
    rows = [r for r in spendledger.load() if r.get("provider") == "glm"]
    by_client = {}
    for row in rows:
        client = row.get("client") or "(no client field)"
        entry = by_client.setdefault(client, {"rows": 0, "cost": 0})
        entry["rows"] += 1
        entry["cost"] += row.get("expected_cost", 0) or 0
    return (len(rows),
            sum((r.get("expected_cost", 0) or 0) for r in rows),
            by_client)


def _read_spend_safely():
    """`_read_spend`, with the failure NAMED instead of reported as zero."""
    try:
        return _read_spend() + (None,)
    except Exception as exc:                                   # noqa: BLE001
        return 0, 0, {}, f"{type(exc).__name__}: {exc}"


# --------------------------------------------------------------- main


def main(argv=None):
    args = parse_args(argv)
    if not args.ledger_client:
        args.ledger_client = args.task

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
    acceptance_missing = not commands
    if acceptance_missing:
        # MEASURED 2026-10-02: this printed "Extracted 0 acceptance commands"
        # and then carried on to ask GLM three questions, one of which is "can
        # the acceptance check fail?" - about a check that was never run, and it
        # could still come back PASS. A verification that skips its own evidence
        # and returns PASS is the worst failure mode available to this script,
        # because the PASS is believed.
        #
        # WHY A CAP AND NOT A REFUSAL. Measured the same day: only 108 of 581
        # task files carry an `## Acceptance` section, and a commit authored
        # outside the qwen-task flow has no task file at all - so refusing
        # outright would make 81% of this repository, and every hand-authored
        # commit, unverifiable. That is not a safer tool, it is an unused one.
        # So the rest of the verification runs and PASS is made UNREACHABLE,
        # enforced after the model answers rather than by asking it nicely.
        headings = 0
        if task_file and os.path.exists(task_file):
            text = open(task_file, encoding="utf-8").read()
            headings = sum(1 for line in text.splitlines()
                           if line.strip().lower().startswith("## acceptance"))
        print("NO ACCEPTANCE COMMANDS - PASS IS NOT AVAILABLE FOR THIS RUN.")
        print(f"  task file            : {task_file or '(not found)'}")
        print(f"  '## Acceptance' heads: {headings}")
        print("  Either the task declares no runnable acceptance, or the "
              "extractor did not understand the section. Either way nothing "
              "executed the task's own claim, so the best verdict reachable "
              "here is NEEDS_CLAUDE.")
    acceptance_output = _run_acceptance_in_worktree(args.branch, commands)
    if acceptance_missing:
        prose = acceptance_text(task_file)
        acceptance_output = (
            "NOTHING WAS RUN. This task declares no runnable acceptance "
            "commands, so there is no evidence here that the branch does what "
            "it claims. Treat question 2 as unanswerable and do not return "
            "PASS on the strength of the diff alone.\n\n"
            "The task's acceptance criteria, stated as prose rather than as "
            "commands, are below. Judge the diff AGAINST THESE - that is what "
            "the branch promised:\n\n"
            + (prose or "(the task states no acceptance criteria at all)")
            + "\n\n" + acceptance_output)
    print(acceptance_output.encode("ascii", "replace").decode("ascii")[:2000])

    # Step 2: Diff analysis
    print("\n--- Step 2: Diff analysis ---")
    changed_files = _changed_files(args.branch)
    diff_stat, diff_full = _diff_against_master(args.branch)
    _base, _head, how = review_range(args.branch)
    # WHICH range was reviewed, printed every time. A report that does not say
    # this cannot be told apart from one that reviewed nothing - and reviewing
    # nothing is exactly what happened to every already-merged branch until now.
    print(f"Review range: {how}  ({(_base or '-')[:8]}..{(_head or '-')[:8]})")
    print(f"Changed files: {len(changed_files)}")
    if not changed_files:
        print("  NO FILES IN RANGE - there is nothing here to verify, and that "
              "is never a PASS.")
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
        diff_stat, diff_full, acceptance_output,
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
    env_file = env_path()
    print(f"  credentials from: {env_file}")
    load_env(env_file)

    n_before, cost_before, _by_before, spend_error = _read_spend_safely()
    if spend_error:
        print(f"  spend ledger unreadable: {spend_error} - the spend figures"
              f" below are UNKNOWN, not zero")

    try:
        result = glm.complete(
            prompt, system=SYSTEM,
            max_tokens=args.max_tokens, timeout=args.timeout,
            ledger_client=args.ledger_client)
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

    # THE CAP, enforced here rather than requested in the prompt. A model that
    # is told "do not return PASS" can still return PASS; a verdict that is
    # overwritten cannot. An empty answer is caught by the same line, because
    # `_parse_verdict` of nothing is not a PASS either.
    if test_error and verdict == "PASS":
        print("  OVERRIDING PASS -> NEEDS_CLAUDE: the tests could not be "
              "run, so \"0 failing\" is an unmeasured zero.")
        verdict = "NEEDS_CLAUDE"
        reason = ("GLM answered PASS but the test run failed to start: "
                  + str(test_error) + ". Original reason: "
                  + (reason or "(none)"))
    if not changed_files and verdict == "PASS":
        print("  OVERRIDING PASS -> NEEDS_CLAUDE: the review range was "
              "empty, so the verdict is about no code.")
        verdict = "NEEDS_CLAUDE"
        reason = ("GLM answered PASS but the review range contained no "
                  "files. Original reason: " + (reason or "(none)"))
    if acceptance_missing and verdict == "PASS":
        print("  OVERRIDING PASS -> NEEDS_CLAUDE: no acceptance command ran, so "
              "nothing executed the branch's own claim.")
        verdict = "NEEDS_CLAUDE"
        reason = ("GLM answered PASS, but no acceptance command was run for this "
                  "task, so the claim was never executed. Original reason: "
                  + (reason or "(none given)"))

    n_after, cost_after, by_after, spend_error_after = _read_spend_safely()
    spend_delta_rows = n_after - n_before
    spend_delta_cost = cost_after - cost_before
    if spend_error_after:
        print(f"  spend ledger unreadable after the call: {spend_error_after}")
    elif spend_delta_rows == 0:
        print("  WARNING: the ledger gained NO glm row for this call. Either the"
              " adapter did not bill it or the ledger is not the one it writes.")
    print(f"  spend by client: "
          f"{ {k: v['rows'] for k, v in sorted(by_after.items())} }")

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
    # THE BRANCH IS PART OF THE NAME, and the head SHA with it. Measured
    # 2026-10-02: two verifications of the SAME task on DIFFERENT branches both
    # wrote `branch-TASK-940.md`, and the second silently overwrote the first -
    # so the PASS on the real branch was replaced by the FAIL on a probe, and a
    # reader of that directory would have seen one verdict where two were
    # produced. A verdict that can be overwritten by the next run is not a record.
    _b, _h, _how = review_range(args.branch)
    head_sha = (_git("rev-parse", "--short", _h).stdout.strip()
                if _h else "norange")
    safe_branch = re.sub(r"[^A-Za-z0-9._-]+", "-", args.branch)[:60]
    out_path = os.path.join(
        out_dir, f"branch-{args.task}-{safe_branch}-{head_sha}.md")

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
