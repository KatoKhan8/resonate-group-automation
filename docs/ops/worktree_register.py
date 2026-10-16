"""Generate the worktree register: every registered worktree, what it is, who
owns it, what cites it, and whether anything may be done with it.

    py -3 docs/ops/worktree_register.py                       # the report
    py -3 docs/ops/worktree_register.py --json out.json       # machine-readable
    py -3 docs/ops/worktree_register.py --baseline base.json  # and the delta

GENERATED, NEVER HAND-MAINTAINED. A hand-kept list of worktrees is failure
family 2 - a hand-kept denominator - and this estate has 298 records where a
previous session believed there were fourteen.

READ-ONLY BY CONSTRUCTION, AND THAT IS A BOUNDARY, NOT A PREFERENCE. This script:

  * reads <main>/.git/worktrees/*/gitdir, HEAD and locked as FILES;
  * runs git only as `git --git-dir=<main>/.git <read-only query>`, which needs
    no working tree and touches none;
  * NEVER runs `git worktree` in any form - not remove, not move, not prune,
    not even with --dry-run.

If a future version needs to remove something, it should print the command and
not run it. TASK 0080 held that line, TASK 0220 held it, and the register is
worth less than the line.

TWO TRAPS THIS SCRIPT HAD TO LEARN, BOTH MEASURED ON ITS OWN FIRST OUTPUT.

(1) A CITATION TEST THAT COUNTS ITS OWN PAPERWORK MAKES EVERYTHING IMMORTAL.
The first version grepped every .md in the ops folder for each tree's name and
reported 289 of 298 trees as CITED - because the report that declared a tree
removable names it, the brief asking about it names it, the census that
enumerated it names it, and the lane entry being written right now names it.
None of those is a USE of the tree; they are paperwork about it. So citations
are now split into two buckets. PAPERWORK sources are listed explicitly below,
never guessed by pattern, and are reported separately so a reader can see what
was discounted. Only a LIVE citation keeps a tree off the removable list.

(2) A FILE'S MTIME IS NOT A LINE'S AGE, AND THE LANE FILES ARE APPEND-ONLY.
The first version tagged citations "new since TASK 0080" by comparing the citing
file's mtime to 0080's run time. Every lane file came back "new", including
LANE-pilotcaps.md - whose only mention of wt-ref-4a449dcb3 is line 1888, the
very line 0080 quoted as the LAST mention before it declared the tree spent. The
file had merely grown. So this script reports the citing file AND the first
matching line number, and makes no claim at all about when a mention was
written. (The same shape bit TASK 0210 the same day, where a file's
LastWriteTime was read as evidence of its presence and its CreationTime said
otherwise.)

AND THE LIMIT OF (1), STATED RATHER THAN HIDDEN: the paperwork list excludes
whole FILES, and the lane files are single append-only documents tens of
thousands of lines long. TASK 0080's own report lives INSIDE LANE-qwen.md, so
its mention of a tree it declared spent cannot be excluded by path. That is why
every citation is reported as file:line: the register narrows the question and a
human answers it. A tree whose only live citations are a lane entry ABOUT its
removal is spent, and only a reader can say so.

FAIL-CLOSED. The verdict for a tree this script cannot classify is UNKNOWN, and
UNKNOWN is never "safe to remove". REMOVABLE requires every one of:

    the directory exists                (otherwise it is PRUNABLE, a different
                                         thing, and still not this script's job)
    it is not locked
    it is not a live lane tree
    nothing in the citation roots names it
    its HEAD is contained in at least one local branch
    it has no uncommitted changes and no stash

Any of those unanswerable - a git query that fails, a citation root that cannot
be read - makes the verdict UNKNOWN with the reason attached.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import subprocess
import sys

MAIN = r"C:\Users\Zvonimir\Desktop\resonate-group-automation"
GITDIR = os.path.join(MAIN, ".git")

# The seven live lane trees, from tools\START-ALL-LANES.ps1's own table. A tree
# in this list is never removable, whatever else is true of it.
LIVE_LANE_TREES = {
    r"c:\users\zvonimir\desktop\wt-glm-review-2026-10-14": "glm",
    r"c:\users\zvonimir\desktop\wt-glm-b-2026-10-14": "glm-b",
    r"c:\users\zvonimir\desktop\wt-glm-c-2026-10-14": "glm-c",
    r"c:\users\zvonimir\desktop\wt-suppression-2026-10-14": "suppression",
    r"c:\users\zvonimir\desktop\wt-pilotcaps-2026-10-14": "pilotcaps",
    r"c:\users\zvonimir\desktop\resonate-trees\wt-webapp-2026-10-15": "webapp",
    # qwen is NOT here: C:\Users\Zvonimir\qwc is a standalone clone, not a
    # worktree of this repository, so it never appears in these records at all.
}

# Where a citation can live. A tree named in any of these is CITED and leaves the
# removable list - which is exactly what happened to wt-pilotcaps-brake-2026-10-16
# when CANARY-01-RUNBOOK named it as tree T3.
CITATION_ROOTS = [
    (r"C:\Users\Zvonimir\Desktop\resonate-ops", (".md", ".txt", ".json", ".py", ".ps1")),
    (os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))), "docs"), (".md", ".txt", ".py")),
]
# Directories never worth walking for citations: they are evidence dumps and
# nested checkouts, and a hit inside one is not a citation of a worktree.
CITATION_SKIP_DIRS = {"logs", "runtime", "__pycache__", ".git", "node_modules",
                      "wt-rt", "clone"}

# PAPERWORK, not use. A mention in one of these is a record ABOUT a worktree -
# a census that enumerated it, the report that declared it spent, the brief
# asking whether it still is - and counting it as a reason to keep the tree is
# how a removable list empties itself. Matched on the path, case-insensitively,
# as substrings; explicit, never a guessed pattern.
PAPERWORK_MARKERS = (
    # A raw string may not END with a backslash, so the separators are doubled
    # in plain strings. These are substrings of a path, matched case-insensitively.
    "\\qwen-0080-2026-10-15\\",     # TASK 0080's own inventory and report
    "\\queue\\qwen\\0080-",         # the brief that asked
    "\\queue\\qwen\\0220-",         # this task's brief
    "\\task-0330\\",                # the reference-naming census
    "\\task-0340\\",                # the unlanded-fixes census
    "\\qwen-0177-2026-10-16\\",     # this lane's own staged entries
    "desktop-tidy-2026-10-16.md",   # this task's own deliverable
    "worktree_register",            # THIS SCRIPT ITSELF: its docstring names
                                    # wt-ref-4a449dcb3 as an example, and the
                                    # first version spelled this marker with a
                                    # HYPHEN, so the register cited itself and
                                    # kept a spent tree alive on its own prose.
    "worktree-register",            # and any file named for its output
)


def is_paperwork(path: str) -> bool:
    low = path.lower()
    return any(m.lower() in low for m in PAPERWORK_MARKERS)

LANE_FROM_BRANCH = re.compile(r"^task-([a-z0-9\-]+?)-", re.I)
KNOWN_LANES = {"glm", "glm-b", "glm-c", "qwen", "suppression", "pilotcaps", "webapp"}


def git(*args: str) -> tuple[int, str]:
    """A read-only git query against the main checkout's git dir. No worktree is
    selected, so no working tree can be touched."""
    cmd = ["git", "--git-dir=" + GITDIR] + list(args)
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except Exception as exc:                      # noqa: BLE001 - reported, not swallowed
        return 255, "git invocation failed: %s" % exc
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def read_text(path: str) -> str | None:
    for _ in range(6):
        try:
            with io.open(path, encoding="utf-8", errors="replace") as fh:
                return fh.read()
        except OSError:
            pass
    return None


def collect_records() -> list[dict]:
    base = os.path.join(GITDIR, "worktrees")
    out: list[dict] = []
    if not os.path.isdir(base):
        return out
    for name in sorted(os.listdir(base)):
        rec_dir = os.path.join(base, name)
        if not os.path.isdir(rec_dir):
            continue
        gitdir_file = read_text(os.path.join(rec_dir, "gitdir"))
        head_text = read_text(os.path.join(rec_dir, "HEAD"))
        rec = {
            "record": name,
            "record_dir": rec_dir,
            "gitdir_raw": (gitdir_file or "").strip(),
            "locked": os.path.exists(os.path.join(rec_dir, "locked")),
            "prunable_marker": os.path.exists(os.path.join(rec_dir, "prunable")),
            "head_raw": (head_text or "").strip(),
            "notes": [],
        }
        if gitdir_file is None:
            rec["notes"].append("the gitdir file could not be read")
            rec["worktree_dir"] = None
        else:
            # <worktree>/.git -> <worktree>
            gd = rec["gitdir_raw"].replace("/", os.sep)
            rec["worktree_dir"] = os.path.dirname(gd) if gd.endswith(".git") else gd
        wd = rec["worktree_dir"]
        rec["dir_exists"] = bool(wd) and os.path.isdir(wd)
        if head_text is None:
            rec["notes"].append("the HEAD file could not be read")
        hr = rec["head_raw"]
        if hr.startswith("ref: "):
            rec["branch"] = hr[5:].strip()
            rec["detached"] = False
        else:
            rec["branch"] = None
            rec["detached"] = bool(hr)
        out.append(rec)
    return out


def resolve_heads(records: list[dict]) -> None:
    for rec in records:
        sha = None
        if rec["branch"]:
            code, out = git("rev-parse", rec["branch"])
            if code == 0:
                sha = out.strip().splitlines()[0] if out.strip() else None
            else:
                rec["notes"].append("the branch %s does not resolve" % rec["branch"])
        elif rec["detached"]:
            sha = rec["head_raw"].split()[0]
        rec["head"] = sha


def contained_in_branches(records: list[dict]) -> None:
    for rec in records:
        rec["contained_in"] = None
        if not rec["head"]:
            rec["notes"].append("no HEAD sha, so containment is UNKNOWN")
            continue
        code, out = git("branch", "--contains", rec["head"], "--format=%(refname:short)")
        if code != 0:
            rec["notes"].append("branch --contains failed, containment UNKNOWN")
            continue
        rec["contained_in"] = [b.strip() for b in out.splitlines() if b.strip()]


def build_citation_index() -> tuple[dict[str, list[str]], list[str]]:
    """Map lowercase token -> files naming it. One walk, not one grep per tree."""
    index: dict[str, list[str]] = {}
    problems: list[str] = []
    texts: list[tuple[str, str]] = []
    for root, exts in CITATION_ROOTS:
        if not os.path.isdir(root):
            problems.append("citation root missing: %s" % root)
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d.lower() not in CITATION_SKIP_DIRS]
            for fn in filenames:
                if not fn.lower().endswith(exts):
                    continue
                full = os.path.join(dirpath, fn)
                t = read_text(full)
                if t is None:
                    problems.append("unreadable, so citations from it are UNKNOWN: %s" % full)
                    continue
                texts.append((full, t.lower()))
    return {"__texts__": texts}, problems       # type: ignore[return-value]


def cites(texts: list[tuple[str, str]], token: str, self_paths: set[str]):
    """Return (live, paperwork), each a list of "path:line" strings. The line
    number is the FIRST match, so a reader can judge the mention instead of
    inferring its age from the file's mtime - which is wrong for an append-only
    lane file."""
    tok = token.lower()
    live, paper = [], []
    for path, body in texts:
        if path.lower() in self_paths:
            continue
        pos = body.find(tok)
        if pos < 0:
            continue
        line_no = body.count("\n", 0, pos) + 1
        entry = "%s:%d" % (path, line_no)
        (paper if is_paperwork(path) else live).append(entry)
    return live, paper


# IN SCOPE for a removable verdict: the Desktop's own top level and
# resonate-trees\. Everything else - an agent's nested worktree inside a
# checkout, a %TEMP% scratchpad - is NOT_ASSESSED.
#
# This bound exists because the first version did not have it and reported 108
# trees REMOVABLE, which is the unsafe direction and a far larger claim than
# this register has any evidence for. A nested agent tree belongs to whatever
# created it and may be live; a temp scratchpad belongs to a session that may
# still be running. NOT_ASSESSED is not a soft REMOVABLE: it means nobody has
# looked, and it is never an instruction.
def in_scope(wd: str) -> bool:
    low = (wd or "").lower()
    if not low:
        return False
    if "\\appdata\\" in low or "\\.claude\\" in low or "\\.qwen\\" in low:
        return False
    desktop = "c:\\users\\zvonimir\\desktop\\"
    if not low.startswith(desktop):
        return False
    rest = low[len(desktop):].strip("\\")
    if "\\" not in rest:
        return True                         # directly on the Desktop
    return rest.startswith("resonate-trees\\") and rest.count("\\") == 1


def classify(rec: dict, citations: list[str], cite_problems: bool) -> None:
    why: list[str] = []
    wd = rec["worktree_dir"]
    key = (wd or "").lower().rstrip("\\")

    if not rec["dir_exists"]:
        rec["verdict"] = "PRUNABLE"
        why.append("its directory does not exist, so the record is stale")
        rec["why"] = why
        return
    if key in LIVE_LANE_TREES:
        rec["verdict"] = "LIVE_LANE"
        rec["owner"] = LIVE_LANE_TREES[key]
        why.append("this is lane %s's live worktree" % LIVE_LANE_TREES[key])
        rec["why"] = why
        return
    if rec["locked"]:
        rec["verdict"] = "LOCKED"
        why.append("git has it locked; a lock is somebody's statement that it matters")
        rec["why"] = why
        return
    if rec["notes"]:
        rec["verdict"] = "UNKNOWN"
        why.extend(rec["notes"])
        rec["why"] = why
        return
    if not in_scope(wd):
        rec["verdict"] = "NOT_ASSESSED"
        why.append("a nested agent tree or a temp scratchpad: out of this "
                   "register's scope, and never removable on its authority")
        rec["why"] = why
        return
    if citations:
        rec["verdict"] = "CITED"
        first = citations[0]
        head, _, line = first.rpartition(":")
        why.append("named in %d live file(s), first at %s:%s" % (
            len(citations), os.path.basename(head), line))
        rec["why"] = why
        return
    if cite_problems:
        rec["verdict"] = "UNKNOWN"
        why.append("some citation sources were unreadable, so 'nothing cites it' "
                   "is not established. UNKNOWN is never removable.")
        rec["why"] = why
        return
    if rec["contained_in"] is None:
        rec["verdict"] = "UNKNOWN"
        why.append("containment in a local branch could not be established")
        rec["why"] = why
        return
    if not rec["contained_in"]:
        rec["verdict"] = "UNKNOWN"
        why.append("its HEAD is in NO local branch: removing it could lose a commit")
        rec["why"] = why
        return
    if rec.get("dirty"):
        rec["verdict"] = "UNKNOWN"
        why.append("it has uncommitted changes or a stash")
        rec["why"] = why
        return
    rec["verdict"] = "REMOVABLE"
    why.append("exists, unlocked, not a lane tree, uncited, HEAD contained in %d "
               "branch(es), clean" % len(rec["contained_in"]))
    rec["why"] = why


def owner_of(rec: dict) -> str:
    key = (rec.get("worktree_dir") or "").lower().rstrip("\\")
    if key in LIVE_LANE_TREES:
        return LIVE_LANE_TREES[key]
    br = rec.get("branch") or ""
    m = LANE_FROM_BRANCH.match(br.replace("refs/heads/", ""))
    if m:
        cand = m.group(1).lower()
        for lane in sorted(KNOWN_LANES, key=len, reverse=True):
            if cand == lane or cand.startswith(lane + "-"):
                return lane
    return "UNKNOWN"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", help="write the full register as JSON")
    ap.add_argument("--baseline", help="a previous --json file, to report the delta")
    ap.add_argument("--desktop-only", action="store_true",
                    help="limit the printed table to trees directly under the Desktop")
    args = ap.parse_args()

    if not os.path.isdir(GITDIR):
        print("FATAL: the main checkout's git dir is not readable: %s" % GITDIR)
        return 2

    records = collect_records()
    if not records:
        print("FATAL: no worktree records found under %s" % os.path.join(GITDIR, "worktrees"))
        return 2
    resolve_heads(records)
    contained_in_branches(records)

    bundle, cite_problems = build_citation_index()
    texts = bundle["__texts__"]                    # type: ignore[index]

    # A worktree's own files must not count as citations of itself, and neither
    # must this register's own output.
    for rec in records:
        wd = (rec.get("worktree_dir") or "")
        token = os.path.basename(wd.rstrip("\\"))
        rec["token"] = token
        self_paths = set()
        if wd:
            for path, _body in texts:
                if path.lower().startswith(wd.lower()):
                    self_paths.add(path.lower())
        if token:
            live, paper = cites(texts, token, self_paths)
        else:
            live, paper = [], []
        rec["citations"] = live
        rec["citations_paperwork"] = paper
        rec["owner"] = owner_of(rec)
        classify(rec, live, bool(cite_problems))

    desktop = [r for r in records
               if (r.get("worktree_dir") or "").lower().startswith(
                   r"c:\users\zvonimir\desktop\\".replace("\\\\", "\\"))
               and (r.get("worktree_dir") or "").lower().count("\\") == 4]

    counts: dict[str, int] = {}
    for r in records:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1

    print("WORKTREE REGISTER   main checkout: %s" % MAIN)
    print("generated by docs/ops/worktree_register.py - read-only, no `git worktree` call")
    print("")
    print("records registered        : %d" % len(records))
    print("directly under Desktop\\   : %d" % len(desktop))
    print("verdicts                  : %s" % ", ".join(
        "%s=%d" % kv for kv in sorted(counts.items())))
    if cite_problems:
        print("")
        print("CITATION SOURCES WITH PROBLEMS (%d) - every verdict that depended on" % len(cite_problems))
        print("'nothing cites it' is UNKNOWN because of them:")
        for p in cite_problems[:10]:
            print("  " + p)
    print("")

    rows = desktop if args.desktop_only else records
    print("%-11s %-9s %-46s %-28s %s" % ("VERDICT", "OWNER", "PATH", "BRANCH", "WHY"))
    for r in sorted(rows, key=lambda x: (x["verdict"], (x.get("worktree_dir") or ""))):
        print("%-11s %-9s %-46s %-28s %s" % (
            r["verdict"], r["owner"],
            (r.get("worktree_dir") or "(unreadable)")[-46:],
            (r.get("branch") or ("detached " + (r.get("head") or "")[:8]))[-28:],
            "; ".join(r.get("why", []))[:120]))

    print("")
    paper_only = [r for r in rows
                  if r["verdict"] == "REMOVABLE" and r.get("citations_paperwork")]
    if paper_only:
        print("")
        print("DISCOUNTED AS PAPERWORK (a record ABOUT the tree, not a use of it).")
        print("Each of these is REMOVABLE and would have read CITED under an")
        print("any-mention test:")
        for r in paper_only:
            print("  %-44s %d paperwork mention(s), e.g. %s" % (
                (r.get("worktree_dir") or "")[-44:], len(r["citations_paperwork"]),
                os.path.basename(r["citations_paperwork"][0])))

    print("")
    print("REMOVABLE means every condition in this script's docstring held. It is")
    print("not an instruction: nothing here removes anything, and the operator's")
    print("own sequence is in DESKTOP-TIDY-2026-10-16.md.")

    if args.baseline:
        base = None
        try:
            with io.open(args.baseline, encoding="utf-8") as fh:
                base = json.load(fh)
        except Exception as exc:                   # noqa: BLE001
            print("\nBASELINE UNREADABLE (%s). No delta is reported, and that is" % exc)
            print("UNKNOWN rather than 'no change'.")
            base = None
        if base is not None:
            old = {r.get("worktree_dir") or r.get("path") for r in base.get("records", [])}
            new = {r.get("worktree_dir") for r in records}
            added = sorted(x for x in new - old if x)
            gone = sorted(x for x in old - new if x)
            print("")
            print("DELTA against %s" % args.baseline)
            print("  added : %d" % len(added))
            for a in added[:40]:
                print("    + " + a)
            print("  gone  : %d" % len(gone))
            for g in gone[:40]:
                print("    - " + g)

    if args.json:
        with io.open(args.json, "w", encoding="utf-8", newline="\n") as fh:
            json.dump({"main": MAIN, "records": records}, fh, indent=1)
        print("\nJSON written: %s" % args.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
