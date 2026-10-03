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


#: How EVERY captured subprocess output in this file is decoded, defined ONCE.
#: MEASURED 2026-10-02 by this branch's own GLM run. `text=True` with no
#: encoding decodes with the LOCALE codec (cp1250 on this machine), the reader
#: thread dies on the first byte it cannot map, `CompletedProcess.stdout` comes
#: back `None`, and the prompt's patch slot silently becomes "(could not
#: generate a diff - answer NEEDS_CLAUDE)". `--name-only` and `--stat` survive
#: because they are ASCII, so the verifier looks healthy while reviewing no code
#: at all - the exact defeat this task exists to end, reached by a second route.
#: git emits patch bytes verbatim, so the only sound policy is utf-8 with
#: replacement: a mangled character is a cosmetic loss, a dead reader is a blind
#: reviewer.
CAPTURE = {"encoding": "utf-8", "errors": "replace"}


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
        capture_output=True, text=True, **CAPTURE,
        cwd=cwd or ROOT, timeout=120)


def main_checkout_root():
    """The MAIN checkout's root, from any worktree, or None if git will not say.

    ONE resolution with two users below - `config/.env` and the spend ledger -
    because the second copy of this logic is how the two would come to disagree.

    `rev-parse --path-format=absolute --git-common-dir` is the one path that is
    identical from the main checkout and from every worktree. A RELATIVE answer
    is refused rather than resolved: `abspath` would resolve it against this
    worktree and put us back inside the tree we are trying to escape. The suite
    lock escapes the same trap the same way.
    """
    out = _git("rev-parse", "--path-format=absolute", "--git-common-dir")
    value = (out.stdout or "").strip() if out.returncode == 0 else ""
    if value and os.path.isabs(value):
        return os.path.dirname(os.path.abspath(value))
    return None


def env_path():
    """The ONE `config/.env`, the main checkout's, from any worktree.

    MEASURED 2026-10-02 and this is why GLM verification never ran today:
    `config/.env` is gitignored, so a worktree created by `git worktree add` has
    NONE, and `load_env(ROOT/config/.env)` from a worktree found nothing. The
    call then failed with `MissingKey: no ZAI_API_KEY in config/.env` and the
    verdict became NEEDS_CLAUDE - a verifier that abstains for an environmental
    reason, reported as if it had considered the code.
    """
    root = main_checkout_root()
    if root:
        candidate = os.path.join(root, "config", ".env")
        if os.path.isfile(candidate):
            return candidate
    return os.path.join(ROOT, "config", ".env")


def ledger_path():
    """The ONE spend ledger, the main checkout's, or None if git will not say.

    MEASURED 2026-10-02, and found by GLM reviewing this file once it could
    actually see it: `spendledger.path()` resolves against `store.queue_path()`,
    which is THIS tree's `work/` - and `work/` is gitignored, so every worktree
    has its own. The main checkout held **39** glm rows while the worktree this
    verifier had been running from held **2**: its own two calls, 30,688
    micro-USD of real money, invisible to the production spend audit. The
    standing rule is that model spend is attributed to a client or a task, and
    an audit that reports clean because it watched an empty file is worse than
    none.

    It also made acceptance command 4 unfailable: a freshly created acceptance
    worktree has no ledger at all, so `0 rows, 0 clients` satisfied an
    `isinstance(..., dict)` assertion that no ledger CONTENT could ever break.
    """
    root = main_checkout_root()
    if not root:
        return None
    return os.path.join(root, "work", "spend-ledger.jsonl")


def bind_spend_to_the_main_ledger():
    """Point BOTH the billing and the reading at that one ledger. Returns it.

    `spendledger.path()` honours `SPEND_LEDGER`, so one environment variable
    moves the WRITE inside `glm.complete` and the READ in `_read_spend`
    together - they must never be two different files, or the verifier bills one
    ledger and audits another. `setdefault`, so an operator who exports
    `SPEND_LEDGER` deliberately still wins.
    """
    resolved = ledger_path()
    if resolved:
        os.environ.setdefault("SPEND_LEDGER", resolved)
    return os.environ.get("SPEND_LEDGER")


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


#: The one path prefix whose patch is shown LAST. Prose cannot be checked for a
#: production caller, a constructible failing input or an arithmetic slip - the
#: three questions this reviewer is asked - so when the patch does not fit the
#: prompt it is the prose that must go, never the code.
PROSE_PREFIX = "docs"


def _diff_against_master(branch):
    """The stat and the FULL patch, with the code first and the prose last.

    MEASURED on this branch, 2026-10-02: its own patch is 68,102 characters, of
    which 35,326 are five markdown files and 32,912 are the code. The prompt has
    room for about 57,000, and `git diff` emits paths in alphabetical order -
    `docs/` before `scripts/` - so the truncation banner cut the CODE and left
    the prose. The reviewer was then told, truthfully, that it had not seen
    enough to answer, and NEEDS_CLAUDE is the correct verdict in that state.
    Ordering the patch code-first makes the whole code change fit with room to
    spare, and spends what is left of the budget on prose.

    Two git calls rather than one, and a fallback to the single call if either
    pathspec is refused: the ordering is a refinement, seeing the patch at all is
    the rule.
    """
    base, head, _how = review_range(branch)
    if not base:
        return None, None
    stat = _git("diff", "--stat", base, head)
    code = _git("diff", base, head, "--", ".", f":(exclude){PROSE_PREFIX}")
    prose = _git("diff", base, head, "--", PROSE_PREFIX)
    if code.returncode == 0 and prose.returncode == 0:
        patch = (code.stdout or "") + (prose.stdout or "")
    else:
        whole = _git("diff", base, head)
        patch = whole.stdout if whole.returncode == 0 else ""
    return (stat.stdout if stat.returncode == 0 else None,
            patch or None)


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
    """Test files added or modified on the branch - NEVER ones it DELETED.

    MEASURED 2026-10-03 on `task-word-contract-enforced`, which deliberately
    deleted a 295-line test whose subject no longer exists and kept its cases in
    a new module. Without `--diff-filter=d` git's changed-file list includes the
    deletion, `_run_tests_in_worktree` runs it, `unittest` answers
    `unittest.loader._FailedTest`, and the branch-level "new test failures not in
    baseline" override turns that into a FAIL for the whole branch.

    So the gate punished the honest removal of a stale test - and buried that
    branch's real findings under a loader error. `_new_test_files` already asked
    git the narrower question with `--diff-filter=A`; this one never did.

    The property that matters is stronger than "not deleted": every file handed
    to `unittest` must exist in the branch the tests run from. That is asserted
    in TASK-969's acceptance rather than re-checked here, because git's own
    filter is the cheapest correct answer and a second existence check in this
    function would be a second authority for the same question.
    """
    base, head, _how = review_range(branch)
    if not base:
        return []
    r = _git("diff", "--name-only", "--diff-filter=d", base, head, "--",
             "tests/")
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


STAGES = ["TODO", "RUNNING", "REVIEW", "REWORK", "DONE",
          "BLOCKED", "BLOCKED_QUOTA"]


def _find_task_file(task_id, branch=None):
    """The task file, preferring the one ON THE BRANCH under review.

    MEASURED 2026-10-02: this searched only the INVOKING tree, so a branch that
    carries its own task file - the normal case, since the file describing a piece
    of work usually lands with it - was verified as if it had no task at all. For
    TASK-942 the file existed on a third branch entirely and nowhere in the tree
    the verifier was running from, and the run reported "task file for TASK-942
    not found" about a task that is written down.

    The branch is asked first because the branch is the thing being judged. A file
    found only in the invoking tree is still used, and the caller is told which,
    because "the task file came from somewhere else" is a fact a reader needs.
    """
    if branch:
        listing = _git("ls-tree", "-r", "--name-only", branch)
        if listing.returncode == 0:
            for line in listing.stdout.splitlines():
                parts = line.strip().split("/")
                if (len(parts) >= 4 and parts[0] == "docs"
                        and parts[1] == "qwen-tasks" and parts[2] in STAGES
                        and parts[3].startswith(task_id + "-")
                        and parts[3].endswith(".md")):
                    blob = _git("show", f"{branch}:{line.strip()}")
                    if blob.returncode == 0:
                        handle, path = tempfile.mkstemp(
                            suffix=".md", prefix="task-from-branch-")
                        with os.fdopen(handle, "w", encoding="utf-8",
                                       newline="\n") as fh:
                            fh.write(blob.stdout)
                        return path
    for d in STAGES:
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


#: How much RAW verbose test output goes into the prompt after the summary.
#: The summary is what answers the reviewer's question; the raw tail is context.
RAW_TEST_TAIL = 6_000


def timeout_reason(failure):
    """The reason text for a part whose call never answered.

    A tooling limit must not read as a judgement about the code. It did read
    that way once: I reported two NEEDS_CLAUDE parts to the operator without
    having read that both were `GlmTimeout`, so "the reviewer abstained" stood
    in for "the call never happened".
    """
    if type(failure).__name__ == "GlmTimeout":
        return ("the part timed out TWICE at the adapter's %ss ceiling - this "
                "is A42, a tooling limit and NOT a finding about the code"
                % getattr(glm, "GLM_TIMEOUT", "?"))
    return "GLM call failed: %s" % type(failure).__name__


def ask_with_one_retry(prompt, *, max_tokens=None, timeout=None,
                       ledger_client=None, complete=None, log=print):
    """Ask once; on a TIMEOUT ask exactly once more. Returns `(result, failure)`.

    MEASURED across four runs of `task-word-contract-enforced` on 2026-10-03:
    parts 3, 4, 5 and 6 answered and PASSED while parts 1 and 2 came back
    `GlmTimeout` every time. That is A42 - the adapter clamps every attempt to
    `GLM_TIMEOUT` (180s) and `--timeout` cannot raise the ceiling it names -
    and A42's own measurement is the fix: on TASK-940 a 57,445-character call
    timed out at 180s and the IDENTICAL repeated call answered. The ceiling is
    marginal, not a law about size.

    ONE retry, not a loop: a part that times out twice is reported as having
    timed out twice. Both attempts are billed, because model spend is
    attributed per call and a retry is a call.

    A failure that is NOT a timeout is not retried - retrying a bad request
    spends money to receive the same refusal.

    `complete` is injectable so this is testable without a provider; it was a
    loop inside `main()` first, which is precisely the shape this repository
    warns about.
    """
    caller = complete or glm.complete
    failure = None
    for attempt in (1, 2):
        try:
            return caller(prompt, system=SYSTEM, max_tokens=max_tokens,
                          timeout=timeout, ledger_client=ledger_client), None
        except Exception as exc:                       # noqa: BLE001
            failure = exc
            log("  GLM call failed (attempt %d of 2): %s: %s"
                % (attempt, type(exc).__name__, exc))
            if type(exc).__name__ != "GlmTimeout":
                break
    return None, failure


def modules_of(test_files):
    """`tests/foo/bar.py` -> `tests.foo.bar`, for the files that are test modules.

    One definition, two users: the runner builds its `unittest` arguments from
    it and the summary attributes verbose lines with it. Two spellings of this
    would mean a module that ran under one name and was counted under another.
    """
    modules = []
    for path in test_files:
        if path.endswith(".py") and path.startswith("tests/"):
            modules.append(path.replace("/", ".").replace("\\", ".")[:-3])
    return modules


def summarise_tests(output, modules, baseline=None):
    """One line per changed test module: how many ran, and how they ended.

    MEASURED 2026-10-03 and this is the fifth defect found in this gate rather
    than in a branch. The prompt carried `test_output[:8000]` - the HEAD of a
    verbose run across every changed module - and on `task-word-contract-enforced`
    that cut before both of the branch's controlling test files. GLM said so
    exactly: "the supplied test-results block contains zero tests from
    tests/test_word_contract_enforced.py (53 tests) or
    tests/test_the_keyless_doors_get_the_contract.py (15 tests)", and FAILED the
    branch for having no evidence its own tests ran. The tests had run and
    passed - 53 OK and 15 OK, verified directly afterwards.

    Truncating the HEAD was the worst available choice: unittest prints the
    failures and the verdict at the END, so the 8,000 characters spent were the
    least informative ones in the run.

    A per-module summary cannot be truncated away: it is one short line per
    module, so it scales with the number of modules rather than with how
    talkative they are. The raw tail follows it, labelled, for context.

    THE SUM IS CHECKED AGAINST THE RUN'S OWN `Ran N tests`. A parser that
    under-counts would hide a module while looking tidy, which is the shape of
    half the defects in this repository - so a mismatch is REPORTED in the
    summary rather than smoothed over.
    """
    lines = output.splitlines()
    per_module = {m: {"ran": 0, "ok": 0, "bad": 0, "skip": 0} for m in modules}

    def classify(word):
        word = word.strip().lower()
        if word.startswith("ok"):
            return "ok"
        if word.startswith(("fail", "error")):
            return "bad"
        if word.startswith("skip") or word.startswith("expected failure"):
            return "skip"
        return None

    def outcome_of(index):
        """The verdict for the test named on `index`, wherever unittest put it.

        MEASURED 2026-10-03, and this is the THIRD defect in this summary, each
        found by the reviewer rather than by me. A two-line window missed three
        tests in `test_task913_writer_contract_five_plus_five`, because a
        `ResourceWarning` block sits between the name and the verdict and the
        `ok` ends up ALONE on its own line with no `...` on it at all:

            test_no_legacy_tuple_in_generate (tests...) ... <path>:331:
            ResourceWarning: unclosed file <...src/generate.py...>
              src = open("src/generate.py", encoding="utf-8").read()
            ResourceWarning: Enable tracemalloc ...
            ok

        Three unread verdicts in a 40-test module read as "40 ran, 37 ok, 0
        failed", and GLM inferred hidden skips in a contract-enforcement module
        and failed the branch. There were no skips: the module ends `Ran 40
        tests ... OK`.

        So the window is bounded by the NEXT test's name rather than by a line
        count, and a bare verdict word on its own line counts.
        """
        for offset in range(0, 40):
            position = index + offset
            if position >= len(lines):
                break
            raw = lines[position]
            if offset and "(tests." in raw and "..." not in raw.split("(tests.")[0]:
                break                      # the next test started; stop here
            text = raw.strip()
            # AND STOP AT THE RUN'S OWN SUMMARY. Without this the scan walks
            # past the last test into `Ran 2 tests` / `OK` and reads the run's
            # final `OK` as that test's verdict - caught by this function's own
            # control test, which fed it a genuinely unreadable verdict and got
            # "all ok" back.
            if (text.startswith(("Ran ", "OK (", "FAILED (", "====", "----"))
                    or text in ("OK", "FAILED")):
                break
            if "..." in text:
                found = classify(text.rsplit("...", 1)[1])
                if found:
                    return found
            elif offset:
                found = classify(text)     # a bare `ok` on its own line
                if found:
                    return found
        return None

    for index, line in enumerate(lines):
        # THE FAILURE BLOCK REPEATS EVERY FAILING NAME, and counting those
        # repeats inflates `ran` by exactly the number of failures. MEASURED
        # 2026-10-03, by GLM, using this function's own control line: the
        # summary claimed 237 where the run said "Ran 232 tests", the gap was
        # 5, and the run had 4 failures and 1 error. `test_generate` read
        # "59 ran, 53 ok, 3 FAILED/ERRORED" - 56 accounted, 3 missing, which is
        # its three failures counted twice.
        #
        # So only the VERBOSE INVOCATION line counts a test. unittest's
        # failure block starts its headers with `FAIL: ` or `ERROR: `, and the
        # verdict for those tests was already read from their invocation line.
        stripped = line.strip()
        if stripped.startswith(("FAIL: ", "ERROR: ")):
            continue
        for module in modules:
            if "(%s." % module in line:
                per_module[module]["ran"] += 1
                verdict = outcome_of(index)
                if verdict:
                    per_module[module][verdict] += 1
                break

    # WHICH failures, by module, so each can be marked BASELINE or NEW.
    #
    # MEASURED 2026-10-03 and this is the sixth gate defect, and mine: the
    # first version of this summary reported "3 FAILED/ERRORED" with no
    # baseline context, and GLM reasonably read five of master's standing
    # failures as the branch's own regressions and FAILED a branch whose full
    # suite then measured 228 against the reference's 228 - 0 new, 0 gone. The
    # gate already loads the baseline and already computes the set difference;
    # it simply was not telling the reviewer. A count without its baseline is
    # the same defect as a name-set compared by its size.
    baseline = baseline or set()
    failing_by_module = {m: set() for m in modules}
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith(("FAIL: ", "ERROR: ")):
            continue
        name = normalise_test_name(stripped.split(None, 1)[1])
        if not name:
            continue
        for module in modules:
            bare = module[len("tests."):] if module.startswith("tests.") else module
            if name.startswith(bare + "."):
                failing_by_module[module].add(name)
                break

    out = ["TEST RESULTS BY MODULE (the branch's own tests):"]
    counted = 0
    new_total, baseline_total = 0, 0
    for module in modules:
        row = per_module[module]
        counted += row["ran"]
        if not row["ran"]:
            out.append("  %-62s NOTHING RAN - treat as unmeasured" % module)
            continue
        unread = row["ran"] - row["ok"] - row["bad"] - row["skip"]
        if row["ran"] == row["ok"]:
            out.append("  %-62s %3d ran, all ok" % (module, row["ran"]))
            continue
        if unread:
            # Never leave a reader to infer what the difference was. GLM read
            # three unread verdicts as hidden skips in a contract module and
            # failed a branch for it; there were no skips.
            out.append("  %-62s %3d ran, %d VERDICTS COULD NOT BE READ - do "
                       "not infer what they were"
                       % (module, row["ran"], unread))
            continue
        failing = failing_by_module[module]
        fresh = sorted(failing - baseline) if baseline else sorted(failing)
        standing = sorted(failing & baseline)
        new_total += len(fresh)
        baseline_total += len(standing)
        if baseline and not fresh:
            state = ("%d ok, %d FAILED/ERRORED, %d skipped - ALL %d FAILURES "
                     "ARE IN THE STANDING BASELINE, so they are master's and "
                     "not this branch's"
                     % (row["ok"], row["bad"], row["skip"], len(standing)))
        elif baseline:
            state = ("%d ok, %d FAILED/ERRORED, %d skipped - %d NEW on this "
                     "branch, %d in the standing baseline"
                     % (row["ok"], row["bad"], row["skip"], len(fresh),
                        len(standing)))
        else:
            state = ("%d ok, %d FAILED/ERRORED, %d skipped - NO BASELINE WAS "
                     "LOADED, so none of these is attributable yet"
                     % (row["ok"], row["bad"], row["skip"]))
        out.append("  %-62s %3d ran, %s" % (module, row["ran"], state))
        for name in fresh[:5]:
            out.append("      NEW: %s" % name)

    declared = None
    for line in lines:
        if line.strip().startswith("Ran ") and "test" in line:
            try:
                declared = int(line.strip().split()[1])
            except (IndexError, ValueError):
                declared = None
    if declared is None:
        out.append("  (the run printed no 'Ran N tests' line, so NOTHING is "
                   "proven to have run)")
    elif declared != counted:
        out.append("  CONTROL FAILED: the run says %d tests ran and this "
                   "summary accounts for %d. Trust the run, not the summary."
                   % (declared, counted))
    else:
        out.append("  control: %d tests accounted for, matching the run's own "
                   "count" % counted)
    if baseline:
        out.append("  THE NUMBER THAT DECIDES ATTRIBUTION: %d NEW failing "
                   "name(s) on this branch, %d standing baseline name(s) among "
                   "the modules it changed. A branch is not responsible for a "
                   "baseline name it merely runs."
                   % (new_total, baseline_total))
    else:
        out.append("  NO BASELINE LOADED - nothing above is attributable to "
                   "this branch rather than to master.")
    return "\n".join(out)


# --------------------------------------------------------------- test runner


def _run_tests_in_worktree(branch, test_files):
    """Check out the branch in a temp worktree, run the tests, return results.

    Returns (failing_names: set, output: str, error: str|None).
    """
    if not test_files:
        return set(), "(no test files to run)", None

    modules = modules_of(test_files)
    if not modules:
        return set(), "(no test modules resolved)", None

    wt_path = None
    try:
        wt_path = _create_worktree(branch, suffix="-tests")
        args = [sys.executable, "-m", "unittest"] + modules + ["-v"]
        try:
            # 600s WAS TOO SMALL AND IT SILENTLY DOWNGRADED A PASS.
            # MEASURED 2026-10-03 on `task-942-token-budget`: 23 changed test
            # modules, both review parts PASS, and the step timed out at 600s -
            # so the override "the tests could not be run, so 0 failing is an
            # unmeasured zero" turned a clean branch into NEEDS_CLAUDE. The
            # override is RIGHT; the budget was wrong, and it scaled with
            # nothing. 1800s is the same shape as the suite's own watchdog:
            # chosen from a measurement (the full suite is ~2,070s for 14,695
            # tests, so a 23-module subset has room) rather than from a round
            # number, and a step that still exceeds it is reported, never
            # silently passed.
            result = subprocess.run(
                args, capture_output=True, text=True, **CAPTURE,
                cwd=wt_path, timeout=TEST_STEP_TIMEOUT)
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
                    **CAPTURE, cwd=wt_path, timeout=120,
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
#:
#: FOUND BY GLM, 2026-10-02, reviewing the commit that introduced the banner it
#: reserves for: 400 does not bound a banner that NAMES the withheld files.
#: Thirty docs files at this repository's typical ~85-character paths is 2,550
#: characters of names alone, so `banner + fitted` could exceed
#: `MAX_PROMPT_CHARS`, the adapter would refuse the prompt, and the verifier
#: would report "GLM call failed" - NEEDS_CLAUDE with no review at all, which is
#: the exact failure this whole task exists to end. The bound is now PROVABLE
#: rather than estimated: the names section is capped at `NAME_BUDGET`, the
#: fixed prose at `BANNER_RESERVE`, and the patch is fitted to
#: `room - BANNER_RESERVE - NAME_BUDGET`, so banner + patch <= room by
#: construction. `test_the_prompt_never_exceeds_the_adapters_bound` holds it and
#: `test_the_fixed_banner_prose_fits_its_reserve` holds the first of the two
#: constants against the prose actually written.
BANNER_RESERVE = 700

#: How long the branch's own changed test modules may take in the review's test
#: step. See the comment at the call site: 600 was not a budget, it was a round
#: number, and it downgraded a PASS to NEEDS_CLAUDE on a branch with 23 changed
#: modules.
TEST_STEP_TIMEOUT = 1_800

#: Hard cap on the NAMES section of a partial-patch banner. Beyond it the names
#: stop and a count takes over: "+14 more". A reviewer needs to know what it is
#: missing, and past a dozen names the useful information is the count and the
#: shape, not the full list.
NAME_BUDGET = 1_200


def split_patch_by_file(patch):
    """One (path, text) per file in a patch, in the order git emitted them.

    The unit a reviewer can lose without being misled is a WHOLE FILE. Cutting
    a patch mid-hunk leaves a function body with no signature and a comment with
    no code, and the reviewer cannot tell which half it is holding.
    """
    sections = []
    current = None
    for line in patch.splitlines(keepends=True):
        if line.startswith("diff --git "):
            if current:
                sections.append(current)
            name = line.split(" b/", 1)[-1].strip() if " b/" in line else "?"
            current = [name, line]
        elif current:
            current[1] += line
        else:                                   # a preamble git rarely emits
            current = ["(preamble)", line]
    if current:
        sections.append(current)
    return [(name, text) for name, text in sections]


def fit_patch(patch, room):
    """As many WHOLE files as fit, plus the names of the ones withheld.

    MEASURED 2026-10-02 and this is the third form of the same defect. The patch
    is ordered code-first, prose last, and the old bound then cut the tail at a
    character count: on TASK-940 that left 30,596 characters unseen INCLUDING the
    end of `main()`, so the reviewer could not answer the one question it is
    asked - does this code have a production caller - and NEEDS_CLAUDE was the
    only honest verdict available to it. Two thirds of a function is not two
    thirds of a review; it is no review with a number attached.

    Whole files instead, and the withheld ones NAMED. A reviewer that knows it
    is missing `docs/glm-reviews/branch-TASK-903....md` can judge whether that
    matters; one that knows it is missing "the last 30,596 characters" cannot.
    Returns `(text, withheld_names)`.
    """
    sections = split_patch_by_file(patch)
    if not sections:
        return patch[:room], []
    kept, withheld, used = [], [], 0
    for name, text in sections:
        if used + len(text) <= room:
            kept.append(text)
            used += len(text)
        else:
            withheld.append(name)
    return "".join(kept), withheld


def name_list(names, budget=None):
    """The withheld names, never longer than `budget` characters.

    Names are listed while they fit and then counted: `"a, b, +14 more"`. The
    count is part of the bound's proof - a banner whose length depends on how
    many files a branch happens to touch is not a reserve, it is a guess, and
    that guess made the adapter refuse the prompt.
    """
    budget = NAME_BUDGET if budget is None else budget
    listed, used = [], 0
    for index, name in enumerate(names):
        candidate = len(name) + 2                       # the ", " that joins
        remaining = len(names) - index
        tail = f"+{remaining} more"
        if used + candidate + len(tail) + 2 > budget:
            if listed:
                return ", ".join(listed) + ", " + tail
            return tail
        listed.append(name)
        used += candidate
    return ", ".join(listed) if listed else "(none)"


def patch_parts(patch, room):
    """The patch as PARTS, each a list of `(name, text)` whole files.

    Operator's decision, 2026-10-02: a branch too large for one prompt is
    reviewed in several calls rather than reviewed partially. The split is by
    WHOLE FILES and the patch arrives already ordered code-first, prose-last, so
    the early parts hold the code.

    A single file larger than `room` becomes its own part. The prompt then
    declares that part a mid-file cut, which is the honest description of it -
    the alternative, dropping the file, would hide a whole file from the review
    while reporting a part count that looks complete.
    """
    sections = split_patch_by_file(patch)
    parts, current, used = [], [], 0
    for name, text in sections:
        if current and used + len(text) > room:
            parts.append(current)
            current, used = [], 0
        current.append((name, text))
        used += len(text)
    if current:
        parts.append(current)
    return parts


def part_sentence(index, parts):
    """One sentence telling this call what the OTHER parts hold.

    Operator's condition: every call gets its part, the branch's whole file
    list, and ONE SENTENCE about the rest. Without it a reviewer cannot tell a
    missing caller from a caller in another part, and the honest answer to that
    uncertainty is NEEDS_CLAUDE - which would make a multi-part review strictly
    worse than a truncated single one, because there would be more chances to
    abstain.

    So the sentence also says what to do about it: name the part, do not abstain.
    """
    total = len(parts)
    if total <= 1:
        return ""
    others = []
    for number, part in enumerate(parts, 1):
        if number == index:
            continue
        others.append(f"part {number} holds {name_list([n for n, _ in part])}")
    return (f"THIS IS PART {index} OF {total} of the branch's patch, split by "
            f"whole files with the code first and {PROSE_PREFIX}/ last. "
            + "; ".join(others) + ". Every file is shown COMPLETE in exactly "
            f"one part, and the branch's full file list is above. A question "
            f"whose answer lies in another part is answered by NAMING THAT "
            f"PART - not by NEEDS_CLAUDE, which is reserved for something no "
            f"part could settle.\n\n")


def render_prompt(branch, task, changed_files, diff_stat, patch,
                  acceptance_output, test_output):
    """The prompt text for one patch body, with nothing decided about fitting.

    Split out of `_build_prompt` so that the ROOM a patch has is computed from
    the same rendering the patch eventually goes into. Two renderings would be
    two authorities for one number, and this file's whole subject is what that
    costs.
    """
    return VERIFY_PROMPT.format(
        branch=branch,
        task=task,
        changed_files="\n".join(f"- {f}" for f in changed_files) or "(none)",
        diff_stat=diff_stat or "(could not generate)",
        diff=patch,
        acceptance_output=acceptance_output or "(no commands extracted)",
        test_output=test_output or "(no new tests or could not run)",
    )


def patch_room(branch, task, changed_files, diff_stat, acceptance_output,
               test_output):
    """How many characters of patch fit, after everything else in the prompt.

    `BANNER_RESERVE` and `NAME_BUDGET` are subtracted here so a banner that
    names files can never push the prompt past the adapter's bound - which it
    did once, found by GLM reviewing the commit that introduced it.
    """
    skeleton = len(render_prompt(branch, task, changed_files, diff_stat, "",
                                 acceptance_output, test_output))
    return (glm.MAX_PROMPT_CHARS - skeleton - len(SYSTEM) - PROMPT_MARGIN
            - BANNER_RESERVE - NAME_BUDGET)


def _build_prompt(branch, task, changed_files, diff_stat, diff,
                  acceptance_output, test_output, part_note=""):
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
        return render_prompt(branch, task, changed_files, diff_stat,
                             part_note + patch, acceptance_output, test_output)

    patch = diff or "(could not generate a diff - answer NEEDS_CLAUDE)"
    room = (glm.MAX_PROMPT_CHARS - len(render("")) - len(SYSTEM)
            - PROMPT_MARGIN)
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
        shown_room = max(0, room - BANNER_RESERVE - NAME_BUDGET)
        fitted, withheld = fit_patch(patch, shown_room)
        if fitted and withheld:
            banner = (f"PARTIAL PATCH: {len(withheld)} of "
                      f"{len(withheld) + len(split_patch_by_file(fitted))} files "
                      f"are NOT shown, and they are whole files rather than a "
                      f"cut: {name_list(withheld)}. Everything you DO see is "
                      f"complete. The patch is ordered code first and "
                      f"{PROSE_PREFIX}/ last, so the withheld files are the "
                      f"prose unless a name above says otherwise. If what you "
                      f"cannot see could change your verdict, the correct "
                      f"verdict is NEEDS_CLAUDE.\n\n")
        elif not fitted:
            # NO whole file fits, so the first one alone is larger than the
            # budget. Found by this module's own test, which expected the
            # opposite: keying the fallback on "nothing was withheld" sent an
            # EMPTY patch with a "partial" banner, which is the worst of the
            # three outcomes - the reviewer is told it is seeing most of the
            # change and is seeing none of it. A declared mid-file cut is worth
            # more than nothing, and it must say that the cut is mid-file,
            # because a half-read file is the state this bound exists to avoid.
            fitted = patch[:shown_room]
            banner = (f"CUT PATCH: the first file is larger than the whole "
                      f"budget, so you are seeing the first {len(fitted)} "
                      f"characters of {len(patch)} and the cut is MID-FILE. "
                      f"{len(withheld)} file(s) are involved: "
                      f"{name_list(withheld)}. The correct verdict is "
                      f"NEEDS_CLAUDE unless what you can see is enough on its "
                      f"own.\n\n")
        else:
            banner = ""
        patch = banner + fitted
    return render(patch)


# --------------------------------------------------------------- verdict


def combine_verdicts(verdicts):
    """The branch's verdict from its parts. Operator's rule, 2026-10-02.

    PASS only if EVERY part is PASS. Any FAIL is the branch's verdict; failing
    that, any NEEDS_CLAUDE is. A conjunction, deliberately stricter than one
    call over a truncated patch, because a part that passed says something only
    about that part.

    No parts at all is NEEDS_CLAUDE, not PASS: a review of nothing is the defect
    this whole tool exists to end, and an empty list is the easiest way to get
    one.
    """
    if not verdicts:
        return "NEEDS_CLAUDE", "no part was reviewed, so nothing was verified"
    for number, (verdict, reason) in enumerate(verdicts, 1):
        if verdict == "FAIL":
            return "FAIL", f"part {number} of {len(verdicts)}: {reason}"
    for number, (verdict, reason) in enumerate(verdicts, 1):
        if verdict != "PASS":
            return verdict, f"part {number} of {len(verdicts)}: {reason}"
    return "PASS", (f"all {len(verdicts)} part(s) PASS"
                    if len(verdicts) > 1 else
                    (verdicts[0][1] or "PASS"))


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
    bound = bind_spend_to_the_main_ledger()
    print(f"Spend ledger: {bound or '(git would not answer - THIS TREE)'}")

    if not _branch_exists(args.branch):
        print(f"ERROR: branch {args.branch!r} does not exist")
        return 2

    task_file = _find_task_file(args.task, args.branch)
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

    # Build the parts. One call each, operator's decision 2026-10-02.
    #
    # THE SUMMARY FIRST, THEN THE TAIL. `test_output[:8000]` cut before the
    # branch's own controlling test files on `task-word-contract-enforced` and
    # FAILED it for having no evidence its tests ran - see `summarise_tests`.
    # The tail rather than the head, because unittest prints the failures and
    # the verdict at the end.
    if test_output:
        summary = summarise_tests(test_output, modules_of(test_files), baseline)
        raw = test_output[-RAW_TEST_TAIL:]
        if len(test_output) > RAW_TEST_TAIL:
            raw = ("(the first %d characters of raw output are not shown; the "
                   "summary above accounts for every module)\n...%s"
                   % (len(test_output) - RAW_TEST_TAIL, raw))
        tests_for_prompt = summary + "\n\nRAW OUTPUT (tail):\n" + raw
    else:
        tests_for_prompt = ""
    room = patch_room(args.branch, args.task, changed_files, diff_stat,
                      acceptance_output, tests_for_prompt)
    parts = patch_parts(diff_full or "", room)
    print(f"\nReview parts: {len(parts)} "
          f"(room {room} chars per part, whole files, code first)")
    for number, part in enumerate(parts, 1):
        size = sum(len(text) for _, text in part)
        print(f"  part {number}: {len(part)} file(s), {size} chars"
              f" - {name_list([n for n, _ in part], 160)}")
    prompts = [
        _build_prompt(args.branch, args.task, changed_files, diff_stat,
                      "".join(text for _, text in part), acceptance_output,
                      tests_for_prompt,
                      part_note=part_sentence(number, parts))
        for number, part in enumerate(parts, 1)]

    if args.dry_run:
        print(f"\n--- DRY RUN ---")
        for number, prompt in enumerate(prompts, 1):
            print(f"Part {number} prompt length: {len(prompt)} chars")
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

    per_part, answers, result = [], [], None
    for number, prompt in enumerate(prompts, 1):
        print(f"\n  --- part {number} of {len(prompts)} "
              f"({len(prompt)} chars) ---")
        result, failure = ask_with_one_retry(
            prompt, max_tokens=args.max_tokens, timeout=args.timeout,
            ledger_client=args.ledger_client)
        if failure is not None:
            per_part.append(("NEEDS_CLAUDE", timeout_reason(failure)))
            answers.append(f"### Part {number}: call failed\n\n{failure}")
            continue
        print(f"  {result['model']} {result['seconds']}s {result['usage']}")
        text = result["content"]
        print(text.encode("ascii", "replace").decode("ascii")[:2000])
        part_verdict, part_reason = _parse_verdict(text)
        print(f"  part {number} verdict: {part_verdict}")
        per_part.append((part_verdict, part_reason))
        answers.append(f"### Part {number} — {part_verdict}\n\n"
                       f"{part_reason}\n\n{text}")

    verdict, reason = combine_verdicts(per_part)
    content = "\n\n".join(answers) or "(no part was reviewed)"
    if len(per_part) > 1:
        print(f"\n  parts: "
              + ", ".join(f"{n}={v}" for n, (v, _r) in enumerate(per_part, 1)))

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
        fh.write(f"Parts: {len(parts)}"
                 + (" (" + ", ".join(
                     f"part {n}={v}" for n, (v, _r) in enumerate(per_part, 1))
                    + ")" if per_part else "")
                 + "\n\n")
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
