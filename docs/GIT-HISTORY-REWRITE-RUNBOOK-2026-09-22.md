# Git history rewrite — runbook for the operator

> ## STATUS: NOT SCHEDULED YET. DO NOT EXECUTE.
>
> **Operator decision, Zvonimir, 2026-09-22: keep this runbook, do not run it.
> He will schedule it for a weekend.** It is not a backlog item for a session
> to pick up, and it is not "blocked" - it is deliberately waiting for a
> window when all three sessions and the Qwen pool can be frozen.
>
> Two things that should happen BEFORE that window, and both are ordinary
> merge requests rather than part of the rewrite (section 8):
>
> 1. **Fix the PII guard** — it is red on master right now, and the newest
>    identifier in history is dated today. A rewrite run against a tree still
>    producing identifiers is stale the moment it finishes.
> 2. **Decide section 0.3** — move the guard's 117 values to a gitignored
>    sidecar, so the rewrite does not leave them in the one file present in
>    every commit.
>
> If neither has happened by the time the window arrives, say so before
> starting rather than proceeding: the rewrite is expensive to run and
> expensive to run twice.

**Written on branch `infra` for Zvonimir to execute. Nothing here has been
run.** A history rewrite is irreversible, changes every commit id in the
repository, and invalidates every clone and worktree. It is not mine to do and
this document does not do it.

Hygiene, not urgency — the repository is private. ISSUE-006 records the
standing position: *"Git history still holds the identifiers; rewriting a
pushed history is the operator's decision."* This is that decision, prepared.

---

## 0. READ THIS BEFORE THE REST: two findings that change the job

### 0.1 The 2026-09-15 cutoff does not work

The brief scopes this to "the commits since 2026-09-15". **Measured, it would
leave 217 commits carrying identifiers behind.**

Scanned every one of the 6,128 blobs in the object database against the
guard's own lists (`FORBIDDEN_NAMES`, `FORBIDDEN_DOMAINS`, `FORBIDDEN_FIGURES`
in `tests/test_fixture_hygiene.py` — 58, 44 and 15 entries), then attributed
them to master's first-parent history. Excluding the guard file itself, which
is section 0.3:

    commits on master, first-parent            874
    commits carrying at least one identifier   595
      before 2026-09-15                        217
      on or after 2026-09-15                   378
    earliest carrying commit            2026-09-09   (the repo's first commit)
    latest  carrying commit             2026-09-22   (today)
    distinct paths ever affected                99
    distinct identifiers                        97

The repository's first commit is 2026-09-09 and it already carries
identifiers. **The rewrite has to start at the root commit, not at a date.**
A date-scoped rewrite is the worst outcome available: it costs the full
disruption of a rewrite and leaves the data in place.

### 0.2 The guard is RED RIGHT NOW, and new identifiers are still arriving

`tests/test_fixture_hygiene.py` fails 3 of 13 on master today.

ISSUE-006 closed on 2026-09-20 at `cecd4223` — *"The PII guard has been red
since the 18th, and a red guard catches nothing"* — reporting 13/13 green.
**132 commits later it is red again.** The files it flags landed on 09-21 and
09-22, after that fix:

    docs/HEYREACH-CADENCES-2026-09-21.md                 2026-09-21
    docs/SLACK-AGENT-HANDOFF-2026-09-22.md               2026-09-22
    docs/qwen-tasks/TODO/TASK-249-...names-a-person.md   2026-09-21
    scripts/batch1_build.py                              2026-09-22
    src/clientapproval.py                                2026-09-21
    tests/test_a_client_can_never_reach_another_client.py 2026-09-22
    tests/test_client_approval_is_a_gate.py              2026-09-21

None is mine; verified against both of this branch's commits.

**Sequencing consequence: fix the guard and get it green BEFORE the rewrite,
not after.** The newest identifier in history is dated today. A rewrite run
against a tree that is still producing them is stale the moment it finishes,
and you do not get to run this twice cheaply.

It is also why nobody noticed: the guard is one red test among **112**
(see `docs/state/SUITE-BASELINE-2026-09-22.md`). A safety guard hidden in a
failing baseline is the ISSUE-006 mechanism exactly, one level up — the guard
is no longer silently red, it is loudly red in a room where everything is
shouting.

### 0.3 The guard file itself holds all 117 values in clear

`tests/test_fixture_hygiene.py` is present in **all 874 commits** and carries
**117 identifiers** in plaintext, because it is the list the scanner scans
for. It is the single largest concentration of this data in the repository.

This needs a decision before the rewrite, and it is a real fork:

- **Redact it too**, and the guard stops working — it has nothing to match.
- **Leave it**, and the rewrite removes the identifiers from 99 files and
  leaves them in the one file that is in every commit. This is not a
  half-measure to be waved through: it would make the rewrite close to
  pointless.
- **Move the lists to a gitignored sidecar before the rewrite**, the way
  `config/suppress.local.txt` already works for the real suppression list —
  the guard's own docstring describes that pattern at line 135. The guard
  loads the sidecar, refuses when it is absent, and the tracked file carries
  only `px-` hashes. **This is the recommendation.** It is also a code change
  with a test, so it is a merge request, not a runbook step.

**Do not start section 3 until 0.3 is decided and merged.**

---

## 1. Blast radius

A rewrite changes every commit id from the root forward.

    worktrees to re-create                  10  (master + 8 qwen + slack-agent + infra)
    local branches                          ~90 (89 described as stale)
    remote                                  origin, GitHub, private
    parallel sessions                        3  (production, slack-agent, infra)
    real commit SHAs cited in tracked *.md  59
    files citing at least one                59

**The 59 cited SHAs are the part specific to this repository.** The problem
register's rules are built on naming commits — *"FIXED means merged with a
regression test"*, and every FIXED row names its commit: `0379958d`,
`abfc844a`, `ac6f7996`, `cecd4223`, `28f4766e`, `d321c2ef`… After the rewrite
every one of those is a dangling reference, and the register's central
guarantee — that a claim can be checked against the commit that made it —
silently stops working. `git-filter-repo` writes a full old→new mapping at
`.git/filter-repo/commit-map`; section 5 uses it to rewrite the references.

---

## 2. Tooling — neither option is installed

    git 2.55.0.windows.5        present
    git-filter-repo             NOT installed
    BFG                         NOT usable — no Java on PATH

**Use `git-filter-repo`.** It is a single Python script, stdlib only, and it
is the tool `git filter-branch`'s own documentation now points to.

    py -3 -m pip install git-filter-repo

This is operator tooling, not a product dependency — "zero third-party deps"
is about what `src/` imports at runtime and is unaffected.

`git filter-branch` is the fallback if installing is unacceptable. It is
built in, roughly two orders of magnitude slower, and its trap here is that it
does not rewrite `.git/packed-refs` or the reflog without extra work, so
identifiers survive in unreachable objects. If you use it, section 6's
verification is mandatory rather than advisory.

---

## 3. The procedure

Every step is a command to run, in order. Stop at the first surprise.

### 3.1 Freeze

Nothing else may commit during this. **Tell the other two sessions to stop and
confirm they have.** Then:

```bash
cd /c/Users/Zvonimir/Desktop/resonate-group-automation
git fetch --all
git status --porcelain                 # must be empty in EVERY worktree
git worktree list                      # note all 10; they all die in 3.3
```

For each of the other nine worktrees: commit or discard, then push its branch.
Anything unpushed at this point is lost.

### 3.2 Back up — this is the rollback and there is no other one

```bash
cd /c/Users/Zvonimir/Desktop
git clone --mirror resonate-group-automation/.git resonate-backup-2026-09-22.git
du -sh resonate-backup-2026-09-22.git       # sanity: non-trivial size
```

A mirror clone carries every ref, including the ones the rewrite will drop.
**Do not delete it until section 6 passes and you have lived with the result
for a week.**

### 3.3 Remove the worktrees

`git-filter-repo` refuses to run in a repository with extra worktrees, and it
is right to: their `HEAD`s would point at commits that no longer exist.

```bash
cd resonate-group-automation
for w in resonate-qwen-2 resonate-qwen-3 resonate-qwen-4 resonate-qwen-5 \
         resonate-qwen-6 resonate-qwen-7 resonate-qwen-8 \
         resonate-qwen-worker resonate-slack-agent resonate-infra; do
  git worktree remove --force "../$w"
done
git worktree prune
git worktree list          # only the main checkout should remain
```

They are re-created in 5.3.

### 3.4 Build the replacement file

`git-filter-repo --replace-text` takes `literal:VALUE==>REPLACEMENT`, one per
line. Build it from the guard's own lists using the **same `px()` hash the
working tree was already redacted with** (`scripts/task189_scrub_pii.py`,
salt `resonate-pii-salt-2026-09-16`), so one entity reads the same in history,
in the redacted docs and in the register.

```bash
py -3 - <<'EOF' > /c/Users/Zvonimir/replacements.txt
import hashlib, sys
sys.path.insert(0, "tests")
from test_fixture_hygiene import (FORBIDDEN_DOMAINS, FORBIDDEN_NAMES,
                                  FORBIDDEN_FIGURES)
SALT = "resonate-pii-salt-2026-09-16"
px = lambda v: "px-" + hashlib.sha256((SALT + v).encode()).hexdigest()[:12]
values = list(FORBIDDEN_DOMAINS) + list(FORBIDDEN_NAMES) + list(FORBIDDEN_FIGURES)
for v in sorted(set(values), key=len, reverse=True):     # longest first
    print(f"literal:{v}==>{px(v)}")
EOF
wc -l /c/Users/Zvonimir/replacements.txt      # expect ~117
```

**Write it OUTSIDE the repository.** It is a plaintext list of every real name
and domain, and committing it would undo the whole exercise.

Longest-first matters: a full name must be replaced before its first name is,
or you get `px-aaa Surname`.

**Known limit, and decide it now:** `--replace-text` is literal and
case-insensitive only for what you give it. It will not catch a name split
across a line break, a URL-encoded domain, or a name inside a base64 blob.
Section 6 measures what is left rather than assuming this was complete.

### 3.5 Rewrite

```bash
cd /c/Users/Zvonimir/Desktop/resonate-group-automation
git filter-repo --replace-text /c/Users/Zvonimir/replacements.txt --force
```

Expect several minutes over 3,264 commits and 6,128 blobs.

`filter-repo` removes `origin` on purpose, so a rewritten history cannot be
pushed to the wrong place by reflex. Section 5.2 puts it back deliberately.

---

## 4. Do not skip: the rewrite does not touch `work/`

`work/` is gitignored and holds 300 real companies and 92 real contacts. It is
**not** in history and is **not** affected — correctly. This runbook does not
change anything about that directory and must not be read as having cleaned
it.

Likewise `config/.env` and `config/suppress.local.txt`: gitignored, untouched,
still the real data, still right.

---

## 5. After the rewrite

### 5.1 Verify locally before anything is pushed

```bash
py -3 scripts/history_pii_scan.py .        # section 6
git log --oneline -5
git rev-list --count master                # ~874, ids all different
```

### 5.2 Force-push, once, having checked

```bash
git remote add origin https://github.com/KatoKhan8/resonate-group-automation.git
git push --force --all origin
git push --force --tags origin
git rev-parse master origin/master         # must agree
```

**This is the irreversible step.** Everything before it is local.

GitHub keeps unreferenced objects reachable by SHA for a period and caches
them in the UI. Old commits may stay fetchable by full id for a while. If that
matters, ask GitHub Support to run a garbage collection after the push — for a
private repository with a small audience this is a judgement call, and the
brief says hygiene, not urgency.

### 5.3 Re-create the worktrees

```bash
cd /c/Users/Zvonimir/Desktop/resonate-group-automation
git worktree add ../resonate-slack-agent slack-agent
git worktree add ../resonate-infra       infra
# the qwen pool, as needed — see docs/qwen-tasks/README.md
```

**Every other session must discard its checkout and take a fresh one.** A
worktree from before the rewrite shares no commits with the new history and
will produce a merge that reintroduces every identifier. Say this to the other
two sessions explicitly; do not assume a `git pull` will sort it out, because
it will appear to.

### 5.4 Rewrite the 59 commit references in docs

```bash
py -3 - <<'EOF'
import re, subprocess, pathlib
m = {}
for line in open(".git/filter-repo/commit-map"):
    old, new = line.split()
    if old != b"old" if isinstance(old, bytes) else old != "old":
        m[old[:8]] = new[:8]
changed = []
for p in pathlib.Path("docs").rglob("*.md"):
    t = p.read_text(encoding="utf-8")
    n = re.sub(r"\b([0-9a-f]{8})\b", lambda x: m.get(x.group(1), x.group(1)), t)
    if n != t:
        p.write_text(n, encoding="utf-8", newline="\n"); changed.append(str(p))
print(len(changed), "files updated"); print("\n".join(changed))
EOF
```

Then re-check by hand: 81 eight-hex tokens appear in markdown and only 59 are
real commits, so the other 22 are ids, hashes and digests that must NOT be
rewritten. The map only contains real commits, so the substitution is safe by
construction — but confirm the count of changed files looks like 59, not 81.

Commit that as one change, with a message saying the history was rewritten and
why.

---

## 6. Verification — the part that decides whether this worked

A rewrite that reports success proves nothing. `docs/state/PROBLEM-REGISTER.md`
is explicit that a derived report is only as good as its last verification, and
that a check which passes because it looked at nothing is worse than no check.

`scripts/history_pii_scan.py` is landed with this runbook on branch `infra`.
It scans **every blob in the object database**, not the working tree, and
reports only `px-` hashes — so its output can be pasted anywhere.

```bash
py -3 scripts/history_pii_scan.py . --summary
```

    BEFORE (measured 2026-09-22, this branch)
      blobs scanned                          6,128
      blobs carrying at least one value        308
      commits carrying (excl. guard file)      595
      distinct identifiers                      97

    AFTER — required
      blobs carrying at least one value          0

**Anything other than zero means the rewrite is incomplete**, and the cause is
almost always section 3.4's known limit: a value that is not a literal byte
match. Investigate before pushing. After 5.2 it is far more expensive.

Then, separately:

```bash
py -3 -m unittest tests.test_fixture_hygiene      # must be 13/13
```

The scanner answers "is it in history". The guard answers "is it in the tree".
They are different questions and passing one is not passing the other.

---

## 7. What this does NOT do, stated so nobody assumes it

- **It does not remove anything from `work/`.** Section 4.
- **It does not make the repository safe to open-source.** It removes the
  values the guard knows about. 97 identifiers were found from a list of 117;
  a name nobody added to `FORBIDDEN_NAMES` is invisible to every tool here,
  including the scanner.
- **It does not fix the guard.** The guard is red today (0.2) and that is a
  separate merge request, which must land first.
- **It does not address the 89 stale branches.** They are rewritten along with
  everything else, and they remain stale.
- **It cannot recover a clone somebody already took.** If the repository was
  ever public or ever cloned by anyone outside, the rewrite does not reach
  that copy. The brief states the repository is private now; "now" is doing
  work in that sentence and only the operator knows the history of it.

---

## 8. Recommended order

1. Fix the PII guard and get it to 13/13 — merge request, production session.
2. Decide 0.3 and move the guard's lists to a gitignored sidecar — merge
   request, with a test.
3. Land whatever else is in flight; a rewrite is cheapest when nothing is open.
4. Freeze all three sessions.
5. Sections 3 → 6 in one sitting. It is not resumable in any pleasant way.
6. Tell every session to re-clone, in writing, before they next commit.

Steps 1 and 2 are the ones with standing value. If the rewrite never happens,
they are still the right changes — and if it happens without them, it will
have to happen again.
