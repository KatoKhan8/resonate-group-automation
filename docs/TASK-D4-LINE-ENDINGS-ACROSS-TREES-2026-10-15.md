# D4: THE TEST THAT PASSES AGAINST BYTES NOBODY COMMITTED

**Made durable by the save sweep of 2026-10-16.** This is the qwen lane's D4
measurement, copied VERBATIM from `resonate-ops/qwen-d4-2026-10-15/entry-part1.md`
and `entry-part2.md` — which are not in any git repository and exist on one disk.
It is reproduced here unchanged because `queue/_STANDING-RULES.md` already leans
on it in two places ("qwen's D4 measured 13 names that flip"; "the repair is
qwen's D4 decision, applied once, to all trees") while the finding itself lived
nowhere a fresh clone could read it.

The measurement scripts are in `docs/ops/d4/`. The raw censuses they produced
(eight ~600 KB JSON files, plus the EOL and index-order dumps) are NOT copied
here: they are regenerable by `docs/ops/d4/census.py` against a named SHA, and
they are bulk rather than finding. If they are needed and the disk is gone, the
scripts rebuild them.

Nothing below has been re-measured by the sweep. Every number in it carries the
SHA it was taken at, as written at the time.

---

---

# TASK 0060 — D4: THE TEST THAT PASSES AGAINST BYTES NOBODY COMMITTED
## qwen lane, 2026-10-15, measurement

**VERDICT: D4 IS CONFIRMED, AND IT IS LIVE RATHER THAN LATENT.** A test's pass
or fail flips between the committed bytes and the working-tree bytes, in two
trees that both print **zero lines** of `git status --short`, at the same SHA.
**13 test names flip**, measured by set in both directions. It is not a
merge-gate hazard in waiting; it is the reason two lanes' absolute failure
counts differed by a fixed amount today.

**One part of `pilotcaps/0130`'s account does NOT survive: its CAUSE.** D4
attributes the CRLF bytes to "the mutation tooling these very tests drive".
That is refuted below — the bytes arrive at **checkout**, before any test runs,
and I reproduced glm's exact on-disk hash in a brand-new worktree that has never
run a test. The *phenomenon* pilotcaps reported is real and under-stated; its
mechanism is somewhere else, and the difference matters, because the fix for
"tooling rewrites source" is not the fix for what is actually happening.

Every number below was measured at
**`74fad6c2f8850c5f340eae8bbfbaf5aecb4cc1fe`** — the tip of this clone's local
`master`. `origin/master` is still `b1f290c84`. Artifacts, scripts and the raw
censuses: `resonate-ops/qwen-d4-2026-10-15/`.

### 1. THE FLIP, BY NAME, BOTH DIRECTIONS

Two worktrees, both created by me from this clone at the same SHA, differing in
**one thing only** — the environment the `git worktree add` ran in. Both left
`git status --short` printing nothing.

                              wt-lane                   wt-plain
    created by                me, as dispatched         me, env -u GIT_CONFIG_SYSTEM
    src/claims.py on disk     368a7aa10944afb3  LF      eb9262c7b314d198  CRLF
    the commit records        368a7aa10944afb3          368a7aa10944afb3
    disk == commit?           YES                       NO
    git status --short        0 lines                   0 lines
    207 names, 6 modules      194 ok, 13 FAIL           207 ok, 0 FAIL

The 13 names, all flipping the same way — **green only against bytes the
repository does not contain**:

    test_task915_customer_outcome_semantic_class.MutationTestNeuterClaimRule.test_claims_py_is_crlf
    test_task916_customer_outcome_negative_controls.MutationTest.test_claims_py_is_crlf
    test_task917_an_outcome_needs_an_object.MutationTest.test_claims_py_is_crlf
    test_task918_third_party_outcomes_and_ps_quality.AMutationTest.test_claims_py_is_crlf
    test_task918_third_party_outcomes_and_ps_quality.BMutationTest.test_copylint_py_is_crlf
    test_task919_third_party_and_ps_generalisation.AMutationTest.test_claims_py_is_crlf
    test_task919_third_party_and_ps_generalisation.BMutationTest.test_copylint_py_is_crlf
    test_task921_assertion_structure.PreservedGreen.test_task915_still_passes
    test_task921_assertion_structure.PreservedGreen.test_task916_still_passes
    test_task921_assertion_structure.PreservedGreen.test_task917_still_passes
    test_task921_assertion_structure.PreservedGreen.test_task918_still_passes
    test_task921_assertion_structure.PreservedGreen.test_task919_still_passes
    test_task921_assertion_structure.PreservedGreen.test_task920_still_passes

Seven are the assertion itself. Its docstring says what it thinks it is doing —
"Files are CRLF - an \n-anchored regex matches zero times" — and then:

    path = os.path.join("src", "claims.py")
    with open(path, "rb") as f:
        data = f.read()
    self.assertIn(b"\r\n", data, "claims.py must be CRLF")

**It asserts a property of the checkout, not of the code.** `src/claims.py` is
LF in the object store and has been at every commit I looked at; the assertion
can only pass in a tree whose checkout converted it. The other six are
`test_task921`'s subprocess runners, which re-run 915-920 and inherit the same
verdict — so the flip is amplified: one wrong premise, thirteen names.

Outcomes were collected from `unittest`'s own result object
(`qwen-d4-2026-10-15/runmods.py`), one line per test id, and diffed as SETS.
The name sets are identical in both trees (207 == 207), so nothing is hiding in
a collection error, and **zero names flip in the other direction**.

### 2. THE MECHANISM, MEASURED IN THREE PARTS

**(a) The bytes come from the checkout, and an environment variable decides.**
`C:\Program Files\Git\etc\gitconfig` (401 bytes, mtime 2026-08-24 22:02:51)
carries `[core] autocrlf = true`. `.gitattributes` pins **only** `*.sh`,
`*.bash`, `*.service`, `*.timer` to `eol=lf`; `.py` and `.md` have no attribute
and are therefore converted on checkout.

But every lane session runs with

    GIT_CONFIG_SYSTEM=C:\Users\Zvonimir\Desktop\resonate-ops\tools\empty-system.gitconfig

a **0-byte** file, set at `tools/lane_watcher.ps1:130` as part of the credential
containment installed 02:10 today. It neutralises the whole system gitconfig —
including, as an undesigned side effect, `core.autocrlf`. So:

    git worktree add --detach ... 74fad6c2f          ->  LF   (== the commit)
    env -u GIT_CONFIG_SYSTEM git worktree add ...    ->  CRLF (!= the commit)

Same command, same SHA, same clone, different bytes. The CRLF blob
`eb9262c7b314d1984a0277776618ba83737ef754` is **byte-for-byte the hash
pilotcaps measured on disk in `wt-glm-review-2026-10-14`** — I reproduced a
long-lived lane tree's content in a worktree seconds old that had never run a
test. That is what refutes the mutation-tooling attribution.

For the record, pilotcaps' own guess — `-c core.autocrlf=false` — was
substantially right, and the control that "killed" it could not have worked:
they checked `core.autocrlf` in `.git/config` and built a control worktree
"WITHOUT the flag", but their session's `GIT_CONFIG_SYSTEM` already pointed at
the empty file, so "without the flag" still meant autocrlf off. The control
could not distinguish the two hypotheses it was asked to separate.

**(b) Why `git status` calls it clean: git's racily-clean rule, not a bug.**
An `autocrlf=true` checkout records in the index (i) the **LF blob hash**, which
equals the commit's, and (ii) the **CRLF file's own size and mtime**. So the
index never disagrees with the commit — measured, `index != COMMIT blob` is
**0** in every tree I censused — and the stat cache matches the disk exactly.

A later git process that cannot see `autocrlf=true` *should* call every text
file modified. It only content-compares entries whose recorded mtime is not
strictly older than the index FILE's own mtime (`is_racy_timestamp`); the rest
are trusted on stat alone, and their stat matches. Measured in a fresh CRLF
worktree, reading the index BEFORE anything refreshed it:

    index FILE mtime (sec)              1792081154
    tracked entries                     2517
    RACY (entry mtime >= index mtime)     485
    git status --short reported           485
    reported SUBSET of racy             True
    racy and not reported                   0
    reported and not racy                   0
    never content-checked at all         2032 of 2517  (81%)

Exact set equality, both directions. The racy set is just "whatever landed in
the final clock tick of the checkout", so **the number is noise**: across five
fresh trees today it read 141, 485, 970, 1009 and 1267, varying with machine
load. The mechanism is not noise.

**(c) And the observation is ORDER-DEPENDENT — the first look changes the
answer, permanently.** `git status` rewrites the index. One run by a process
that CAN see `autocrlf=true` marks those entries up to date, and from then on
the autocrlf-blind process reports a clean tree forever:

    wt-plain2, my env (autocrlf blind)      1009 modified
    same, again                             1009 modified
    same, again                             1009 modified
    ONE run, env -u GIT_CONFIG_SYSTEM          0 modified   (correct, for it)
    my env again                               0 modified
    my env again                               0 modified
    ...while the census still reports        2421 files differing from the commit

So **whether this tree looks clean is a fact about which git last looked at it**,
not about the bytes. A lane session, the operator's own shell and any editor or
tool subprocess that does not inherit the env var are three different
`autocrlf` regimes acting on one index.

### 3. HOW WIDE: THIS IS THE DEFAULT STATE, NOT AN EDGE CASE

`qwen-d4-2026-10-15/census.py` compares, for every tracked path, the commit's
blob, the index's blob, and a `sha1` of `blob <len>\0` plus the raw bytes,
computed in Python — no git, so no clean filter, no stat cache, no autocrlf.
Read-only plumbing (`ls-tree`, `ls-files`) only, so no tree is mutated by being
looked at.

**This clone, `C:\Users\Zvonimir\qwc`, at `74fad6c2f`:**

    tracked under src/ scripts/ tests/ config/ docs/   2429
    disk != COMMIT blob                               2420
    disk != INDEX  blob                               2420
    index != COMMIT blob                                 0
    git status --short, whole repository            0 lines

**2,420 of 2,429.** Every one CRLF on disk with zero bare LF. D4 is not 15
names' worth of drift in two long-lived trees — in this clone it is the
condition of 99.6% of the tracked files under those five prefixes, and git
reports the repository clean. By extension: 1,265 `.py`, 1,079 `.md`, 48
`.json`, the rest config and data.

The **nine** files that do hold the committed bytes are the control that proves
the mechanism, because each is an exception for a nameable reason:

    scripts/pool.sh  pool_dispatch.sh  pool_watchdog.sh  provision_worktrees.sh
    scripts/server/deploy.sh  scripts/server/provision.sh  stage_work_to_host.sh
          -- eight files, and .gitattributes pins *.sh text eol=lf
    src/__init__.py                 -- 0 bytes: no newline to convert
    docs/qwen-tasks/TODO/TASK-1016-the-lane-watcher-pulls-its-own-work.md
          -- LF: written by a lane session today, after 02:10, and never
             re-checked-out. The exception that dates the regime change.

`.gitattributes` works. It is simply only asked about shell scripts, and it was
added for a reason worth re-reading: a CRLF `set -euo pipefail` broke a
provisioning run over ssh on 2026-09-23.

### 4. THE TASK'S NAMED CANDIDATE, AND WHY IT IS A DIFFERENT DEFECT

`docs/requests/2026-01-01-aaaa.md` is rewritten on every suite run, but **not by
git**. `tests/test_invariants` drives `slackrequests.write()` through
`_writers()`; `src/slackrequests.py:603` opens the ticket with
`open(tmp, "w", encoding="utf-8")` — text mode, no `newline=`, so Python
translates every newline that `render()` joined into `os.linesep`. On Windows
that is CRLF. Confirmed directly: a two-line text-mode write lands
`b'a\r\nb\r\n'`.

The arithmetic says it is exactly the same conversion:

    commit    4ec179fc...  433 bytes   23 LF,    0 CRLF
    in qwc    e28dec00...  456 bytes    0 LF,   23 CRLF        433 + 23 = 456

Which produces a result worth stating plainly. In an **LF** tree the rewrite is
a real 433-to-456 byte change, the mtime moves, git re-hashes, and `git status`
shows it — that is why glm and pilotcaps had to `git restore` it. In a **CRLF**
tree the rewrite lands the bytes that were already there, so there is nothing to
see. **In this clone that file is already CRLF and `git status` calls it clean.**
The suite's artefact is visible precisely in the trees where it is a genuine
change, and invisible in the trees that were already wrong — so the lane that
restores it is the lane that was measuring correctly.

Also worth separating: `slackrequests.write()` calls
`store.refuse_production_write(path)` first, but `docs/requests/` is not under
`work/`, so the barrier does not apply and the file is written for real. That is
a test leaving an artefact in the repository, which the module's own comment at
`src/slackrequests.py:58-62` says must not happen. Named, not fixed.

### 5. THE PREMISE CHECK ON `pilotcaps/0130`, ITEM BY ITEM

    "tests that pass only against silently-modified working-tree bytes,
     in trees git status calls clean"                        CONFIRMED, 13 names
    "a merge-gate hazard"                                    CONFIRMED, and live
    "the identical 15"                                       NOT REPRODUCED: 13
    "rewritten ... by the mutation tooling these very tests drive"   REFUTED
    "core.autocrlf is false in the shared .git/config"       TRUE but not the
                                                             authority; the
                                                             SYSTEM config is,
                                                             and the env var
                                                             decides who sees it
    the 15-name delta cancels exactly in their verdict       UNCHALLENGED - all
                                                             13 flip one way, so
                                                             a reference and a
                                                             branch measured in
                                                             the same byte regime
                                                             do cancel. Their
                                                             CERTIFIED stands.

On the count: their surviving artefact
`pilotcaps-halt-cert-2026-10-15/set-tip.txt` lists **14** names in this family,
not 15. Thirteen are the flips above. The fourteenth is
`test_invariants.TestNothingCanSend.test_no_module_issues_an_http_post_outside_the_named_ones`,
and at `74fad6c2f` it **FAILS in both byte regimes** — so it is not
line-ending-dependent here and I cannot carry it as a flip. It reads source with
`.splitlines()`, which handles CRLF. Whether it flipped at their SHA
(`1ea8105bf`) is UNKNOWN to me; settling it needs a run at that lineage, which
this task's one-suite budget did not cover. The fifteenth name is unaccounted
for in their own artefact. **Their verdict is unaffected either way** — a
cancelling constant does not change a delta — but the number to quote is 13
measured, 14 in their file.


### 6. THE SUITE'S OWN FOOTPRINT: ONE FILE, AND IT IS VISIBLE

One offline suite run, in a detached worktree I created and own, at the same
SHA, launched only after a self-checked process read found no suite anywhere on
the machine and both clones' lock files absent.

    command           py -3 scripts/run_suite.py --offline
    tree              %TEMP%\qwen-d4\wt-suite   (detached 74fad6c2f, mine)
    launched          2026-10-15T16:17:30Z
    wall_seconds      2243.1
    timed_out         False
    results_reached   14806
    failures_are_partial  False
    result_line       FAILED - 179 failure(s), 70 error(s) of 14851
    status            FAIL, 253 names

**That 253 is not comparable to any other lane's number** and I am not offering
it as a baseline: different SHA, different clone, and 13 of the 253 are the
flips in section 1, which are red here precisely because this tree holds the
committed bytes. It is reported only to show the run was COMPLETE —
`timed_out=False`, `failures_are_partial=False`, 14,806 verdicts reached — so
the census either side of it means something.

**The census, before and after the same run, same tree:**

                                     BEFORE        AFTER
    tracked under the five prefixes   2429          2429
    disk != COMMIT blob                  0             1
    disk != INDEX  blob                  0             1
    index != COMMIT blob                 0             0

Repeated over **every** tracked path with no prefix limit: 2,517 files hashed,
**1** differing. The whole list is one name:

    docs/requests/2026-01-01-aaaa.md    commit 4ec179fc  ->  disk e28dec00
                                        433 bytes, 23 LF  ->  456, 23 CRLF

    git status --short                  1 line:  M docs/requests/2026-01-01-aaaa.md
    untracked artefacts left (-uall)    0

So **the answer to "how wide is the suite's rewriting" is: one tracked file, and
`git status` reports it.** The suite is not the vector for D4. Its one artefact
is the Python text-mode write of section 4, it is caught by the ordinary tooling
in a tree that matches its commit, and it is the file both other lanes correctly
restored. For completeness, `e28dec00` is the same hash this file carries in
`qwc` — Python's `os.linesep` write and an `autocrlf=true` checkout produce
byte-identical output, confirmed across two independently-produced trees.

### 7. THE FLIP-TEST ANSWER, AND WHY THE NAMED CANDIDATE CHECK WOULD NOT HAVE CAUGHT THIS

**The flip-test answer is YES** — 13 names, section 1, live and not latent.

But the two measurements together settle something about the remedy, and it is
the most useful thing this task produced. The task named one candidate:

> a suite that records the tree's blob-hash rollup before and after itself and
> refuses to report a verdict if they differ

**Measured, that check does not catch D4.** The drift that makes 13 tests lie is
present **before the suite starts** — 2,420 files in `qwc`, 2,421 in a fresh
CRLF worktree, all of it written at checkout. A before/after comparison is
blind to it by construction: the rollup is the same wrong rollup at both ends,
the check reports NO DIFFERENCE, and the verdict is published. The only thing
it would have flagged is the one file above, which `git status` already flags.

This is the same shape as the defect itself. A before/after rollup asks "did I
change?" when the question is **"am I what the commit says?"** An equality
between two measurements of the same wrong tree is not evidence about the tree.

### 8. THE PROPOSAL: A PRE-FLIGHT IDENTITY CHECK, COSTED

Smallest honest form. A check, not a fix. Not implemented.

**P0 — refuse to publish a suite verdict from a tree that is not its commit.**
Two halves, because they are two different questions and only one of them is
hard:

    (1) index vs COMMIT      git diff-index --cached --quiet HEAD
                             blob against blob. No stat, no filter, no working
                             tree. Reliable. Measured exit 0 in every tree.

    (2) worktree vs INDEX    MUST be content-derived, NEVER stat-derived.
          cheap, eol only    git ls-files --eol   ->  flag any  i/X w/Y, X != Y
                             0.44s for 2517 files. Reads the files; writes
                             nothing; safe to run read-only in a tree you do
                             not own.
          complete           sha1("blob <len>\0" + raw bytes) per tracked file,
                             compared to the index sha, rolled into one sha256.
                             1.64s for 2517 files. Catches any content drift,
                             not only line endings.

Validated on three trees before proposing it:

    tree                    git status   ls-files --eol mismatches   truth
    wt-lane     (LF)          0 lines          0                     clean
    wt-plain2   (CRLF)        0 lines       2509                     2421 drifted
    qwc         (CRLF)        0 lines       2508                     2420 drifted
    wt-suite    (post-run)    1 line           1                     1 drifted

Where it goes: `scripts/run_suite.py`, after `suitelock.acquire` and before
`run_suite()`. The verdict file gains `tree_matches_commit=` and, when false,
the drifted names; and `status=` becomes **UNUSABLE** rather than PASS or FAIL.
That is invariant 0 applied to the gate's own input: an authority that cannot
be trusted reads UNKNOWN, and UNKNOWN never becomes PASS.

Cost: roughly 20 lines, one new helper, no new state, no new config, no new
dependency; 0.44s on a 2,243s run, which is **0.02%**, or 1.64s for the
complete version. Against that: every suite verdict stops being able to
describe a tree other than the one it ran in.

**THE PART THAT MATTERS MOST, AND IT CORRECTS `pilotcaps/0130`'s OWN
RECOMMENDATION.** D4 recommends "a `git diff --quiet` after
`git update-index --refresh`, which defeats the stat cache". **Measured, it does
not defeat the stat cache, and it returns PASS on the tree that matters:**

    on wt-plain2  (status 0 lines, 2421 files really drifted)
        git update-index --refresh         exit 0
        git diff --quiet                   exit 0     <- gate would PASS
        git diff-index --quiet HEAD        exit 0     <- gate would PASS
        git update-index --really-refresh  exit 0
        git diff --quiet                   exit 0     <- gate would PASS

    on wt-stat2   (same bytes, but no autocrlf-aware git has refreshed it yet)
        git update-index --refresh         exit 1
        git diff --quiet                   exit 1     <- caught, this time

`--refresh` and `--really-refresh` both compare **stat**, not content;
`--really-refresh` only additionally ignores the assume-unchanged bit. So the
git-native check gives the right answer in a tree nobody has looked at yet and
the wrong answer in a tree that has been used — which is the worse of the two
failure modes, because it is confident, intermittent, and resolves toward PASS
the longer a tree lives. **No stat-based command can see this. Only a content
read can.** That is the whole reason P0's half (2) is specified as
content-derived rather than as a git convenience.

**P1 — the named before/after rollup: keep it, but for its real hazard, and
not as the D4 guard.** Cost 2 x 1.64s = 3.3s per run, 0.15%. What it is good
for is the thing this repository has actually done once: tooling that mutates
tracked source mid-run, which CLAUDE.md warns about by name. It must **report
the names rather than refuse**, because in a correct LF tree it will fire on
every single run until the Python write in `slackrequests.write()` is fixed —
and a check that fires every run is a check somebody disables.

**P2 — not a check, and it would remove the need for P0 entirely.** One line in
`.gitattributes`:

    * text=auto eol=lf

The checkout then produces the committed bytes regardless of `core.autocrlf`
and regardless of whether a session inherits `GIT_CONFIG_SYSTEM`. Cost: one
line, a renormalising checkout in every existing tree, and — **in the same
change, not after it** — the 13 assertions of section 1, because they assert
the opposite and would become permanently red. That is a code change, so it is
named here and not done.

### 9. THE 13 TESTS ARE THEMSELVES THE DEFECT

Worth saying plainly, since the proposal above only makes the hazard visible.
`test_claims_py_is_crlf` and its six copies assert a property of **somebody's
checkout**. No one wants "claims.py must be CRLF" to be true — `.gitattributes`
exists in this repository specifically because CRLF in a working tree broke a
production provisioning run. The smallest honest repair is to read the bytes
from the object store (`git cat-file blob HEAD:src/claims.py`) if the test needs
them at all, or to delete the assertion. Either is a code change and is not in
this task's scope.

### 10. AN INCIDENTAL FINDING THAT BEARS ON "ONE SUITE PER MACHINE"

`src/suitelock.py` resolves through `--git-common-dir`, which CLAUDE.md
describes as "the one path that is identical from the main checkout and from
every worktree". It is — **within one clone.** There are at least two
independent clones on this machine:

    C:/Users/Zvonimir/qwc                              -> C:/Users/Zvonimir/qwc/work/suite.lock
    C:/Users/Zvonimir/Desktop/resonate-group-automation -> .../resonate-group-automation/work/suite.lock

Two files. My run took the first; a run launched from the main clone or any of
its ~230 registered worktrees would take the second and **would not have waited
on mine**. The lock is per-CLONE, not machine-wide, and the operator's rule is
machine-wide. This did not affect today's measurement — I read both lock paths
immediately before launching, found both absent, and a self-checked
`Get-CimInstance Win32_Process` read (538 processes, own pid visible) found no
`run_suite`, `tests.offline` or `unittest discover` process anywhere. Filed,
not fixed; it is a one-line change to resolve the lock from a machine-wide path
instead, and it is not this task's.

### 11. OPEN DECISION FOR THE OPERATOR — DO NOT WAIT ON IT

**Which comes first, P2 or P0?** They interact and the order is his call, not
mine, because one of the two orders has an operational cliff.

- **P0 first** is the honest measurement and an immediate cliff: every existing
  tree on this machine, `qwc` included, fails the pre-flight at once, so every
  suite verdict reads UNUSABLE and the merge gate stops until the trees are
  renormalised. That is the check being right, not wrong — but it stops work.
- **P2 first** removes the cause, after which P0 is a cheap guard that is green
  from the day it lands.

**My recommendation: P2, then P0, in that order, with the 13 assertions deleted
or re-pointed at the blob inside P2's own change.** The reason is the one
CLAUDE.md gives for the whole gate — a reference bound to something that can
move is not a reference. Fixing the checkout makes the bytes stop moving;
adding P0 first only tells us, loudly and continuously, that they already have.

### 12. WHAT IS UNKNOWN, AND WHAT IS UNFINISHED

- **The 15th name in `pilotcaps/0130`'s delta is UNKNOWN.** Their own artefact
  carries 14. Settling whether
  `test_invariants...test_no_module_issues_an_http_post_outside_the_named_ones`
  flipped at `1ea8105bf` needs a run at that lineage; `b77cd4b20` and
  `1ea8105bf` are **not objects in this clone** (`git cat-file -t` says so), so
  it also needs the main clone, which this task may not touch. Authority that
  would settle it: a two-tree flip test at `1ea8105bf` in the clone that holds
  it. Not re-queued; a file has to be written for it to happen.
- **Nothing else is unfinished.** The one suite run completed inside this run
  and its verdict is above; no background job of mine is still alive.

### 13. HOUSEKEEPING

- **One** full suite run, as budgeted. Its lock was created and removed by
  `run_suite.py` itself at `C:\Users\Zvonimir\qwc\work\suite.lock`; I read both
  clones' lock paths before launching and **never created, took, moved or
  deleted a lock file by hand**. No other lane's lock was touched. Lock
  confirmed absent again after the run.
- Six worktrees created, all mine, all detached at `74fad6c2f`, all under
  `%TEMP%\qwen-d4\`: `wt-lane`, `wt-plain`, `wt-plain2`, `wt-stat`, `wt-stat2`,
  `wt-stat3`, plus `wt-suite`. Removed and pruned at the end of the run; see
  the readback below.
- **No lane's worktree was entered.** The two long-lived trees `pilotcaps/0130`
  named were never written to and never had a git command run in them; their
  state is quoted from pilotcaps' own report, and the only thing I added about
  them I reproduced in a tree of my own. `census.py` uses `ls-tree` and
  `ls-files` only, neither of which refreshes or rewrites an index, and the
  disk-side hashing is pure Python with no git involved at all.
- `qwc` itself: HEAD unchanged, `git status --short` 0 lines before and after. I
  deliberately ran **no** `update-index`, `add`, `restore`, `checkout` or
  `stash` in it — which matters here more than usual, because section 2(c)
  shows that merely refreshing its index changes what every later reader sees.
- No code and no test changed. Nothing committed, pushed or merged. No branch
  created. `b1f290c84` not removed — measured present as a commit object and,
  in this clone, the **parent** of the SHA everything above was measured on
  (`git merge-base --is-ancestor` true, `b1f290c84..HEAD` is exactly 1 commit,
  TASK-1016).
- **A push from this clone is impossible by construction, and that is measured
  rather than promised:** `git remote -v` in `qwc` prints nothing and
  `refs/remotes/` holds **zero** refs. Which also means **this clone cannot
  verify `origin/master`** — the `b1f290c84` figure is taken from
  `queue/_STANDING-RULES.md`, a secondary source, and reading the real one
  would need a `git fetch`, which is a network call this task does not name.
  Labelled accordingly in section 0 above rather than asserted.
- No provider, Apify, Slack or network call. No cap, gate or copy change.
  `CLIENT_CHANNEL_GAG` untouched. `config/.env` never read — the suite tree had
  none and I did not supply one. No watcher started, stopped or restarted; the
  26 monitor loops seen in the process read were left alone.
- Artefacts: `resonate-ops/qwen-d4-2026-10-15/` — `census.py`, `runmods.py`,
  `stat_forensics.py`, `stat2.py`, `stat3.py`, the before/after censuses as
  JSON, `mods-wt-lane.tsv` / `mods-wt-plain.tsv` (the flip, by name),
  `first-status.txt`, `eol-wt-plain2.txt`, `suite.launch`,
  `suite_verdict-74fad6c2f.txt`.
