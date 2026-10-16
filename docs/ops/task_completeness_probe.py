#!/usr/bin/env py -3
"""Did a lane task finish, and can that be proven? - qwen TASK 0171.

WHY THIS EXISTS. On 2026-10-16 the qwen watcher logged `START 0170` at 00:58:53
and then nothing at all - no DONE, no TIMEOUT, no `watcher down.`. The brief for
0171 named two worlds: 0170 was killed partway (its work incomplete), or it ran
to completion as an orphan and only the record is missing. Redoing complete work
costs a lane-hour; assuming completeness ships a half-finished change.

THE DEFECT THIS IS BUILT AGAINST. `DONE\\<name>` is a FILENAME, and as of
02:00 on 2026-10-16 nine of them read `exit1` for briefs that never ran. A
filename is not a measurement. Neither is a lane entry on its own: `glm/0055`
committed a real fix and wrote no entry, and for four hours the fix was invisible
- the record and the work are INDEPENDENT, and this estate has shipped each one
without the other.

So the verdict has TWO LEGS and they are reported separately, never merged:

    RECORD  can a fresh reader find out what happened?
            commit, report artefact, lane entry, task stdout, watcher DONE line
    WORK    does the thing the brief asked for exist and run?
            declared artefacts present, declared tests green

Four verdicts, because "complete" and "incomplete" cannot carry the case that
actually occurred:

    COMPLETE            both legs pass. Nothing to do.
    ORPHAN_WORK         WORK passes, RECORD does not. The work is on disk; write
                        the record. DO NOT REDO.
    INCOMPLETE          WORK fails. Finish it - from the partial, not from zero.
    UNKNOWN             a leg could not be read. Never a pass. Names the file it
                        would need, per the standing rule on UNKNOWN.

FAIL-CLOSED, AND THE REASON IS THIS ESTATE'S SIXTH FAILURE FAMILY. A
completeness check that calls everything complete is worse than none, because it
is believed - B7 shipped exactly that. So an unreadable leg is UNKNOWN rather
than passing, and `--control-must-not-pass` makes a case's FAILURE the exit
condition, so the probe is run against a known-bad case and is itself falsified.
"""

import argparse
import os
import subprocess
import sys


#: Verdicts. Ordered worst-to-best so a reader cannot mistake the ranking.
UNKNOWN = "UNKNOWN"
INCOMPLETE = "INCOMPLETE"
ORPHAN_WORK = "ORPHAN_WORK"
COMPLETE = "COMPLETE"


class Check(object):
    """One readable fact. `ok` is tri-state: True, False, or None for UNKNOWN.

    None is not False. A missing lane file and a lane file with no entry are
    different findings, and collapsing them is how "no evidence" becomes
    "evidence of absence" - the thing invariant 0 forbids.
    """

    def __init__(self, leg, name, ok, detail, authority=None):
        self.leg = leg
        self.name = name
        self.ok = ok
        self.detail = detail
        #: The file that would settle it, named only when `ok is None`.
        self.authority = authority

    def __str__(self):
        mark = {True: "PASS", False: "FAIL", None: "UNKNOWN"}[self.ok]
        line = "  [%-7s] %-6s %-22s %s" % (mark, self.leg, self.name, self.detail)
        if self.ok is None and self.authority:
            line += "\n             authority needed: %s" % self.authority
        return line


def _git(repo, *args):
    """Run git, returning (exit, stdout). stderr is CAPTURED, never discarded.

    The standing rule is explicit: a measurement's stderr sent to /dev/null
    became a false "the lock is free" on 2026-10-02. A git command that fails
    here must be able to say so.
    """
    proc = subprocess.run(["git", "-C", repo] + list(args),
                          capture_output=True, text=True)
    if proc.returncode != 0:
        return proc.returncode, proc.stderr.strip()
    return 0, proc.stdout.strip()


def check_commit(repo, token, ref="HEAD"):
    """Is there a commit REACHABLE FROM THIS LANE'S REF whose subject names this task?

    SCOPED TO ONE REF, AND THAT IS A CORRECTION. The first version searched
    `--all --reflog`, and on its first real use it PASSED 0170 on the strength of
    `cc112ae60 "TASK 0170: the nine measured on ONE tree"` - which is
    *pilotcaps*' task 0170, on `integ/canary-nine-2026-10-15`, nothing to do with
    qwen. A bare task number is not a lane-unique identifier: seven lanes number
    their briefs from the same sequence, so eight different `0170`s exist across
    this estate's queues. The leg that decides whether work was committed was
    being answered by another lane's commit.

    So the question is scoped to the ref the lane is on. The standing rule that
    `glm/0055`'s fix "was on a branch the worktree was not standing on" is still
    honoured - but by naming the ref to search, not by searching everything and
    accepting any match. Hits on OTHER refs are reported as a warning, never as
    the pass, because that is the ambiguity that produced the false positive.
    """
    code, out = _git(repo, "log", ref, "--oneline", "--grep=" + token, "-i")
    if code != 0:
        return Check("RECORD", "commit", None, "git log failed: %s" % out,
                     authority="git log %s --grep in %s" % (ref, repo))
    # What else in the repository answers to the same number, for the warning.
    _, elsewhere = _git(repo, "log", "--all", "--oneline", "--grep=" + token, "-i")
    others = [l for l in elsewhere.splitlines() if l and l not in out.splitlines()]
    if not out:
        detail = "no commit on %s names %r" % (ref, token)
        if others:
            detail += (" -- NB %d commit(s) elsewhere do, and they are NOT this "
                       "lane's: %s" % (len(others), others[0][:60]))
        return Check("RECORD", "commit", False, detail)
    return Check("RECORD", "commit", True,
                 "%d commit(s) on %s, newest: %s"
                 % (len(out.splitlines()), ref, out.splitlines()[0]))


def check_artifact(repo, relpath, leg, name):
    """Does a declared file exist and hold something?

    An empty file is FAIL, not PASS. `task-qwen-20261016-005853.out` was 0 bytes
    and a zero-byte artefact is the signature of a process that never reached
    its own ending.
    """
    if relpath is None:
        return Check(leg, name, None, "no path declared for this task",
                     authority="the task brief")
    full = os.path.join(repo, relpath) if not os.path.isabs(relpath) else relpath
    if not os.path.exists(full):
        return Check(leg, name, False, "absent: %s" % relpath)
    size = os.path.getsize(full)
    if size == 0:
        return Check(leg, name, False, "present but EMPTY (0 bytes): %s" % relpath)
    return Check(leg, name, True, "%d bytes: %s" % (size, relpath))


def check_lane_entry(lane_file, token):
    """Is there a heading in the lane file naming this task?

    Headings only. A task id appears in prose constantly - 0160's own entry ends
    by saying it is starting 0170 - so a substring search over the whole file
    would have called 0170 recorded on the strength of its predecessor's
    sign-off. That is the exact shape of a false pass.
    """
    if not os.path.exists(lane_file):
        return Check("RECORD", "lane-entry", None, "lane file absent",
                     authority=lane_file)
    try:
        with open(lane_file, "r", encoding="utf-8", errors="replace") as fh:
            heads = [ln.rstrip() for ln in fh if ln.startswith("#")]
    except OSError as exc:
        return Check("RECORD", "lane-entry", None, "unreadable: %s" % exc,
                     authority=lane_file)
    hits = [h for h in heads if token.lower() in h.lower()]
    if not hits:
        return Check("RECORD", "lane-entry", False,
                     "no heading names %r (%d headings read)" % (token, len(heads)))
    return Check("RECORD", "lane-entry", True, "heading: %s" % hits[-1][:90])


def check_done_line(watch_log, brief_name):
    """Did the WATCHER itself record an ending for this brief?

    The watcher is the only authority for its own ledger, and this is the one
    check a task cannot forge about itself. A START with no DONE is the orphan
    signature. Read from the log, never from a DONE/ filename - nine of those
    were positively false on 2026-10-16.
    """
    if not os.path.exists(watch_log):
        return Check("RECORD", "watcher-DONE", None, "watcher log absent",
                     authority=watch_log)
    starts, dones = [], []
    with open(watch_log, "r", encoding="utf-8", errors="replace") as fh:
        for ln in fh:
            if brief_name not in ln:
                continue
            if "] START " in ln:
                starts.append(ln.strip())
            elif "] DONE " in ln or "] TIMEOUT " in ln:
                dones.append(ln.strip())
    if not starts and not dones:
        return Check("RECORD", "watcher-DONE", None,
                     "brief never appears in the watcher log",
                     authority=watch_log)
    if not dones:
        return Check("RECORD", "watcher-DONE", False,
                     "START with NO ending: %s" % starts[-1][:88])
    return Check("RECORD", "watcher-DONE", True, dones[-1][:88])


#: `FAIL: name (dotted.path)` / `ERROR: name (dotted.path)` in unittest's
#: closing summary. Parsed into a NAME SET, because of the operator rule: a
#: baseline is a named list and is compared by set, never by count. Three
#: finished suites each reported 231 failures and one was a different 231.
_FAILURE_PREFIXES = ("FAIL: ", "ERROR: ")


def _failing_names(text):
    names = set()
    for ln in text.splitlines():
        ln = ln.strip()
        for pre in _FAILURE_PREFIXES:
            if ln.startswith(pre):
                names.add(ln[len(pre):].split(" ")[0])
    return names


def check_tests(repo, modules, baseline=()):
    """Do the task's own test modules pass, right now, in this tree?

    THIS IS THE LEG THAT CANNOT BE FAKED BY A RECORD. A fabricated commit and a
    hand-written lane entry satisfy every RECORD check; only running the code
    distinguishes work that exists from work that is claimed. Run directly
    through unittest, never `run_suite.py`, so no suite lock is taken - one full
    suite at a time is an operator rule and this probe is not a suite.

    COMPARED BY NAME SET, NEVER BY EXIT CODE. The first version of this function
    read `returncode != 0` as FAIL and the positive control caught it at once:
    `tests.test_fixture_hygiene` carries 5 of this repo's 231 known-failing
    names, so a task that demonstrably finished read INCOMPLETE. An exit code
    cannot tell a regression from a baseline this tree has carried all week.
    So the question is NEW names: `failing - baseline`. An empty `baseline` is
    the right default only for a module BORN with the change, which is the case
    this probe was built for; for a pre-existing module the baseline must be
    passed in, measured on the same SHA and the same tree.
    """
    if not modules:
        return Check("WORK", "tests", None, "no test modules declared",
                     authority="the task brief")
    env = dict(os.environ)
    env.pop("LANE_DEADLINE", None)  # the probe is not a lane leg
    proc = subprocess.run([sys.executable, "-m", "unittest"] + list(modules),
                          cwd=repo, capture_output=True, text=True, env=env)
    blob = (proc.stderr or "") + "\n" + (proc.stdout or "")
    ran = next((l.strip() for l in blob.splitlines() if l.startswith("Ran ")),
               None)
    if ran is None:
        # No "Ran" line at all means the modules did not even load - an import
        # error, a syntax error, a half-applied change. UNKNOWN, not FAIL:
        # nothing was measured. Fail-closed either way, never a pass.
        return Check("WORK", "tests", None,
                     "modules did not run (no 'Ran' line); exit=%d" % proc.returncode,
                     authority="py -3 -m unittest %s in %s" % (" ".join(modules), repo))
    failing = _failing_names(blob)
    new = sorted(failing - set(baseline))
    if new:
        return Check("WORK", "tests", False,
                     "%s - %d NEW failing name(s): %s"
                     % (ran, len(new), ", ".join(n.split(".")[-1] for n in new[:4])))
    extra = (" (%d baseline name(s) still failing, 0 new)" % len(failing)
             if failing else "")
    return Check("WORK", "tests", True,
                 "%s - 0 new failing names%s (%s)" % (ran, extra, ",".join(modules)))


def probe(repo, lane_file, watch_log, token, brief_name,
          report=None, out_file=None, artifacts=(), modules=(),
          baseline=(), deliverable="code", ref="HEAD"):
    """Run both legs and return (verdict, checks).

    `deliverable` exists because the positive control failed without it. 0160
    was a MEASUREMENT task - its brief asked for a report and no code - so
    demanding a green test module of it asked for something nobody ordered, and
    the probe called a finished task INCOMPLETE. For a measurement task the
    report IS the work product, so it is checked on both legs; for a code task
    the tests are.
    """
    checks = [
        check_commit(repo, token, ref),
        check_artifact(repo, report, "RECORD", "report"),
        check_lane_entry(lane_file, token),
        check_done_line(watch_log, brief_name),
    ]
    if out_file:
        checks.append(check_artifact(repo, out_file, "RECORD", "task-stdout"))
    for rel in artifacts:
        checks.append(check_artifact(repo, rel, "WORK", "artefact"))
    if deliverable == "measurement":
        checks.append(check_artifact(repo, report, "WORK", "measurement"))
    else:
        checks.append(check_tests(repo, modules, baseline))

    work = [c for c in checks if c.leg == "WORK"]
    record = [c for c in checks if c.leg == "RECORD"]

    # WORK is evaluated first and strictly. A failing or unreadable WORK leg
    # settles the verdict on its own: no amount of record proves code runs.
    if any(c.ok is False for c in work):
        return INCOMPLETE, checks
    if any(c.ok is None for c in work):
        return UNKNOWN, checks
    if all(c.ok is True for c in record):
        return COMPLETE, checks
    if any(c.ok is None for c in record):
        return UNKNOWN, checks
    return ORPHAN_WORK, checks


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", required=True)
    ap.add_argument("--lane-file", required=True)
    ap.add_argument("--watch-log", required=True)
    ap.add_argument("--token", required=True,
                    help="task id as it appears in a commit subject / heading")
    ap.add_argument("--brief-name", required=True,
                    help="brief filename as the watcher logs it")
    ap.add_argument("--report", default=None)
    ap.add_argument("--out-file", default=None)
    ap.add_argument("--artifact", action="append", default=[])
    ap.add_argument("--module", action="append", default=[])
    ap.add_argument("--baseline-failure", action="append", default=[],
                    help="A test name KNOWN to fail on this tree before the "
                         "change. Compared by set; an exit code cannot tell a "
                         "regression from this repo's standing 231.")
    ap.add_argument("--ref", default="HEAD",
                    help="The ref whose history is searched for the task's "
                         "commit. Defaults to HEAD. NOT --all: a bare task "
                         "number is not lane-unique and another lane's 0170 "
                         "passed this check once.")
    ap.add_argument("--deliverable", choices=("code", "measurement"),
                    default="code",
                    help="What the brief actually ordered. 'measurement' tasks "
                         "ship a report and no code; demanding tests of one "
                         "made the positive control read INCOMPLETE.")
    ap.add_argument("--control-must-not-pass", action="store_true",
                    help="Invert the exit code: this case is KNOWN not to be "
                         "complete, so COMPLETE is the failure. Without a run "
                         "like this the probe has never been falsified.")
    args = ap.parse_args()

    verdict, checks = probe(args.repo, args.lane_file, args.watch_log,
                            args.token, args.brief_name, args.report,
                            args.out_file, args.artifact, args.module,
                            args.baseline_failure, args.deliverable,
                            args.ref)

    print("TASK %s -- %s" % (args.token, args.brief_name))
    print("  repo %s" % args.repo)
    for c in checks:
        print(c)
    print("VERDICT: %s" % verdict)

    if args.control_must_not_pass:
        if verdict == COMPLETE:
            print("CONTROL FAILED: a case known to be incomplete read COMPLETE. "
                  "The probe is blind and its other verdicts are worth nothing.")
            return 1
        print("CONTROL HELD: not COMPLETE, as required.")
        return 0
    return 0 if verdict == COMPLETE else 2


if __name__ == "__main__":
    sys.exit(main())
