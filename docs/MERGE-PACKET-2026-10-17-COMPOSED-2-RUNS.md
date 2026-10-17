# LANDING PACKET - COMPOSED-2-RUNS, both orders

TASK merge/0390. Lane: merge. Tree: `C:\Users\Zvonimir\Desktop\resonate-trees\wt-merge-2026-10-16`
(worktree of the shared checkout; `git-common-dir` measured as
`C:/Users/Zvonimir/Desktop/resonate-group-automation/.git`).

    HEAD at measurement   0f48d5c4e86862fa6bf8c1d170b1c53edfb66ea5
    origin/master         b1f290c847eb2500b7eb39987ac34f6d6a8d00d2
    probe window          2026-10-17T15:49:53Z .. 2026-10-17T15:52:53Z
    porcelain after every probe    empty (0 lines); HEAD never moved; no ref touched

Every expected value below was printed by a probe run in this task, in this tree,
inside that window. Nothing is copied from prose. Where a value could not be
recomputed it is marked UNKNOWN and names the authority that would have been
needed.

## 0. Verdict and controls

**ISSUED.** The three controls reproduce 0370's recorded answers:

| control | 0370's answer | this task's reproduction | probe |
|---|---|---|---|
| ff rc | 0 | rc 0 - `merge-base --is-ancestor b1f290c84 <branch>` is 0 for BOTH branches | `git merge-base --is-ancestor` |
| true-merge rc | 1 | rc 1 - `merge-base --is-ancestor A B` is 1, and `B A` is 1 | `git merge-base --is-ancestor` |
| composed tree | `9fde760a...` | `9fde760a6758dfba9522251f4d397ce0c4777f48`, rc 0, one line of output, IDENTICAL in both orders | `git merge-tree --write-tree` |

Two readings of "ff"/"true-merge" are both reported, so a disagreement cannot hide
in the choice of instrument. The ancestry instrument gives rc 0 / rc 1 as above;
the merge-tree instrument gives the ff SIGNATURE (a ff returns the tip's own tree)
for `master vs A` -> `b7a575217...` (A's own tree) and `master vs B` ->
`67c7a40f6...` (B's own tree), both rc 0 with no conflict output. The composed
merge-tree is rc 0 and conflict-free in both orders.

## 1. Measured constants

Probe names are exact commands; run from the tree named above. `--write-tree`
lines are the tree oid on line 1.

| # | name | value | probe |
|---|---|---|---|
| 1 | origin/master (as last fetched) | `b1f290c847eb2500b7eb39987ac34f6d6a8d00d2` | `git rev-parse origin/master` |
| 2 | provenance of that cache | `FETCH_HEAD` mtime `2026-10-16 16:19:18.934272500 +0200` | `ls -l --time-style=full-iso <git-common-dir>/FETCH_HEAD` |
| 3 | refs/heads/master (this checkout's local) | `5fc5784fc364a182f71082997119550c97bd1b7f` | `git rev-parse refs/heads/master` |
| 4 | local master vs origin master | local IS an ancestor of origin, rc 0; origin is NOT an ancestor of local, rc 1; merge-base = `5fc5784fc...` (1 commit apart) | `git merge-base --is-ancestor`, `git merge-base`, `git rev-list --count` |
| 5 | branch A tip | `cbe9d05e7413b0383d2329c3dc59d25d9f1205c9` = `refs/heads/task-merge-0320-f1-writer-repair-2026-10-17` | `git rev-parse`, `git name-rev`, `git for-each-ref` |
| 6 | branch B tip | `0355fe7b72c9497b12819c37d16795a66039c943` = `refs/heads/task-glm-c-0164-brake-ship` | same |
| 7 | both tips also on the remote | `refs/remotes/origin/task-merge-0320-...` and `.../task-glm-c-0164-brake-ship` at the SAME two SHAs | `git for-each-ref` |
| 8 | A contains master / B contains master | rc 0 / rc 0 | `git merge-base --is-ancestor b1f290c84 <branch>` |
| 9 | A vs B, either direction | rc 1 / rc 1 | `git merge-base --is-ancestor A B`, `... B A` |
| 10 | master tree | `d85cd444371b4261d64f0c00199954031341dddb` | `git rev-parse b1f290c84^{tree}` |
| 11 | local-master tree | `d85cd444371b4261d64f0c00199954031341dddb` - **the SAME object** | `git rev-parse 5fc5784fc^{tree}` |
| 12 | branch A tree | `b7a575217e7ac2338e74a227da1697f6752b4aa2` | `git rev-parse A^{tree}` |
| 13 | branch B tree | `67c7a40f6c0397040f79a28e43590ba21c81b174` | `git rev-parse B^{tree}` |
| 14 | COMPOSED tree | `9fde760a6758dfba9522251f4d397ce0c4777f48`, one object, both orders | `git merge-tree --write-tree A B` and `... B A` |
| 15 | commits each branch adds over master | A: 13, B: 2 | `git rev-list --count b1f290c84..<branch>` |
| 16 | A's parent / B's parent | `7018cf28dca5c72a2d0fa1736f9446610d2450a5` / `68af064ee341645f05b1beb6f1986fb588999885` | `git rev-list --parents -n 1` |
| 17 | changed paths per branch | A: 6 (1 M, 5 A); B: 19 (11 M, 8 A) | `git diff --name-status master <branch>` |
| 18 | intersection of the two path sets | **0 paths** (6 + 19 = 25) | `git diff --name-only` x2, `sort`, `comm -12` |
| 19 | composed tree vs B tip | exactly A's 6 paths | `git diff --name-status B 9fde760a...` |
| 20 | composed tree vs A tip | exactly B's 19 paths | `git diff --name-status A 9fde760a...` |
| 21 | commits anywhere carrying the composed tree | **0 of 9866** | `git log --all --format='%H %T' \| grep 9fde760a...` |
| 22 | commits carrying A's tree / B's tree | 1 / 1 | same scan |
| 23 | merge.ff | unset (rc 1) - `git merge` fast-forwards when it can | `git config --get merge.ff` |
| 24 | merge.renormalize | unset (rc 1) - so merge-tree's tree is the tree `git merge` will write | `git config --get merge.renormalize` |
| 25 | merge.conflictStyle, .gitattributes merge drivers | unset (rc 1); none (grep rc 1) | `git config --get`, `grep merge .gitattributes` |
| 26 | core.autocrlf (shared repo config) | `true` | `git config --get core.autocrlf` |
| 27 | remote | `origin https://github.com/KatoKhan8/resonate-group-automation.git`; `remote.origin.fetch = +refs/heads/*:refs/remotes/origin/*` | `git remote -v`, `git config --get` |
| 28 | ff diffstat, order 1 | `6 files changed, 2287 insertions(+)` | `git diff --shortstat master A` |
| 29 | ff diffstat, order 2 | `19 files changed, 2120 insertions(+), 12 deletions(-)` | `git diff --shortstat master B` |
| 30 | merge diffstat, order 1 (A -> composed) | `19 files changed, 2120 insertions(+), 12 deletions(-)` | `git diff --shortstat A 9fde760a...` |
| 31 | merge diffstat, order 2 (B -> composed) | `6 files changed, 2287 insertions(+)` | `git diff --shortstat B 9fde760a...` |
| 32 | empty-diff proof, post-ff | `git diff <tip> <tip>`: rc 0, **0 bytes**, for A and for B | `git diff`, `wc -c` |
| 33 | non-empty counterexample | `git diff A B --stat` -> 25 files, `2120 insertions(+), 2299 deletions(-)`; `git diff B 9fde760a --stat` -> 6 files, `2287 insertions(+)` | `git diff --stat` |
| 34 | .github/suite-baseline.txt | ABSENT at `b1f290c84`; PRESENT at `cbe9d05e7` | `git cat-file -e <sha>:<path>` |
| 35 | scripts/ci_suite.py | ABSENT at `b1f290c84`; PRESENT at `cbe9d05e7` | `git cat-file -e` |
| 36 | scripts/run_suite.py, scripts/glm_verify_branch.py, src/suitelock.py | all EXIST at `b1f290c84` | `git cat-file -e` |

Constants 1-36 are bound to `origin/master` still being `b1f290c84`. **If step 0
disagrees, this whole packet is VOID** - every tree id, rc and diffstat below is a
function of those four SHAs (master, A, B, composed), not of the branch names.

## 2. Why the price is exactly 2 runs, and which run is the next reference

The gate (CLAUDE.md): a merge may land only if the branch's full suite run shows
ZERO NEW NAMES against a reference measured on the master it is merging into; and
one run serves as both gate and next reference when the branch already CONTAINS
master, because then the tree of master-after-merge equals the branch's own tree.

    run R1 = full suite on branch-1's tree, diffed against the reference on b1f290c84
    run R2 = full suite on branch-2's tree, diffed against R1

- **Landing 1 is a fast-forward** (constant 8: the branch contains master, rc 0).
  Master-after is the branch's tip commit itself. So master-after's tree IS R1's
  tree and master-after's commit IS the commit R1 measured. R1 is therefore both
  the gate for landing 1 and the reference on the new master. **1 run.**
- **Landing 2 cannot fast-forward** (constant 9: rc 1 in both directions). The
  merge commit is new, its tree is `9fde760a...` (constant 14), and that is
  neither branch's tree (constants 12, 13, 33). R2 gates landing 2 but is **not** a
  reference on the final master. **1 run.**

    total = 2.

- Not 1: R1 never measured the other branch's paths (6 and 19 paths, disjoint -
  constants 17, 18). Landing 2 introduces every one of them.
- Not 4: no run is needed on the composed tree *for landing 2 itself*. The
  composed tree only becomes somebody's master when a THIRD branch merges into it.
- **Which run is the next reference:**
  - after landing 1: **R1** is the reference on the new master, and the proof that
    it may be reused is the empty-diff obligation in section 5 (CLAUDE.md:
    "the emptiness of that diff is proven every time, never assumed").
  - after landing 2: **no run is a reference on the final master.** The +1 in
    section 7 is exactly that missing reference.
- Both orders cost the same 2 and produce the same composed tree, because
  `merge-tree` returns one object either way (constant 14). The orders differ only
  in which branch's tree is the intermediate master, and hence in **which run sets
  the reference**:

    ORDER 1 (A then B):  intermediate master = A, tree b7a575217..., reference R1 = A's run
    ORDER 2 (B then A):  intermediate master = B, tree 67c7a40f6..., reference R1 = B's run

## 3. STEP 0 - freshness, identical for both orders

Run in the clone that will land. This task was forbidden the network and could not
run these two lines itself; they are the operator's, and they are the only step
that converts the local tracking cache into the remote.

    git fetch origin
    git rev-parse origin/master
    git ls-remote origin refs/heads/master
    git rev-parse cbe9d05e7 0355fe7b7
    git rev-parse refs/heads/master          # the checkout's own master, note 2 below

EXPECT, at 40 hex each:

    origin/master             b1f290c847eb2500b7eb39987ac34f6d6a8d00d2
    ls-remote refs/heads/master   the same 40 hex
    cbe9d05e7                 cbe9d05e7413b0383d2329c3dc59d25d9f1205c9
    0355fe7b7                 0355fe7b72c9497b12819c37d16795a66039c943

ABORT if `rev-parse origin/master` and `ls-remote` disagree, or if either branch
tip differs from the 40 hex above. **Every expected value in this packet is bound
to those four SHAs; on any disagreement the packet is VOID, not adjusted.**

Two notes the operator needs at this exact step:

1. **The tracking ref is a cache.** The value in constant 1 is `origin/master` as
   last fetched, and this tree's last fetch is `FETCH_HEAD` mtime
   `2026-10-16 16:19:18.934272500 +0200` (constant 2). Only `ls-remote` speaks to
   the remote. Until it returns `b1f290c84`, step 0 has not been performed.
2. **This checkout's local master is not `origin/master`.** Measured:
   `refs/heads/master` = `5fc5784fc364a182f71082997119550c97bd1b7f`, one commit
   BEHIND, `b1f290c84`'s parent (constant 4). Both are named in `_STANDING-RULES.md`
   and the divergence is the operator's. **No content readback can detect which one
   the merge started from**: `5fc5784fc^{tree}` and `b1f290c84^{tree}` are the same
   object (`d85cd444...`, constants 10, 11) because `b1f290c84` is an empty commit
   ("PROBE: ... Empty - no file changes"). The wrong-base tell is therefore NOT the
   diffstat - `git diff --shortstat 5fc5784fc A` prints `6 files changed, 2287
   insertions(+)`, byte-identical to the correct-base figure (constants 28, 29).
   The ONLY readback that separates them is `git rev-parse HEAD` at the merge step.
   Normalise first, which is a pure fast-forward and rewrites nothing:

       git switch master
       git merge --ff-only b1f290c847eb2500b7eb39987ac34f6d6a8d00d2
       git rev-parse HEAD        # must now be b1f290c847eb2500b7eb39987ac34f6d6a8d00d2

## 4. ORDER 1 - `cbe9d05e7` then `0355fe7b7`

A = `cbe9d05e7413b0383d2329c3dc59d25d9f1205c9`. B = `0355fe7b72c9497b12819c37d16795a66039c943`.

### STEP 1 - run R1 on A's tree

    (tree checked out at cbe9d05e7413b0383d2329c3dc59d25d9f1205c9)
    py -3 scripts/run_suite.py

EXPECT: the suite completes and its log is written. It takes 2100-2720s alone and
takes the machine-wide lock (`src/suitelock.py`, which exists at `b1f290c84`,
constant 36). Do not start a second full suite anywhere on this machine.

ABORT: if the run does not finish, R1 does not exist and landing 1 cannot be gated.
There is no partial R1.

### STEP 2 - gate R1

Diff R1's failing-name set against the reference measured on `b1f290c84`:
**ZERO NEW NAMES required.**

EXPECT: zero new names. ABORT on any new name: the branch does not land.

PRECONDITION this task could not verify: R1 must have been measured in a tree whose
line-ending flavour matches the reference's, or the name-set comparison is void
(the standing rule on trees - a reference measured in one tree is not automatically
valid in another). The reference's own provenance is UNKNOWN here: reading it means
reading a suite log, and `_EXTERNAL-MODEL-RULES.md` section 7 forbids this lane
`logs\*.out`. Authority needed: the reference log the gate actually consumes. Also
note `merge.renormalize` is unset (constant 24), so the merge is not content-rewriting
in a way that would change a name set.

### STEP 3 - land A as a fast-forward

    git switch master
    git rev-parse HEAD          # ABORT unless b1f290c847eb2500b7eb39987ac34f6d6a8d00d2
    git merge --ff-only cbe9d05e7413b0383d2329c3dc59d25d9f1205c9

EXPECT: `Fast-forward` and a diffstat of exactly `6 files changed, 2287
insertions(+)` (constant 28). git abbreviates the sha pair in its own `Updating
<old>..<new>` line; only `git rev-parse` output is authoritative at 40 hex.

    git rev-parse HEAD
    # cbe9d05e7413b0383d2329c3dc59d25d9f1205c9
    git rev-parse HEAD^{tree}
    # b7a575217e7ac2338e74a227da1697f6752b4aa2      (constant 12)

ABORT: if `merge --ff-only` refuses, the ff precondition no longer holds - stop and
re-measure section 4's constants; do not fall back to a merge commit without
re-deciding the run accounting, because a non-ff landing 1 changes what R1 is a
reference on. If the tree is not `b7a575217...`, stop: nothing below is valid.

### STEP 4 - the CLAUDE.md emptiness proof, before R1 is reused

Mandatory, and it is the reason R1 may serve as the next reference at all:

    git diff HEAD cbe9d05e7413b0383d2329c3dc59d25d9f1205c9

EXPECT **EMPTY - 0 bytes of output, rc 0** (calibrated on the identical pair:
constant 32; a non-empty result looks like constant 33). Corroborate with the
stronger, non-content check that HEAD is the same COMMIT, not merely the same tree:

    git merge-base --is-ancestor HEAD cbe9d05e7413b0383d2329c3dc59d25d9f1205c9   # rc 0

**ABORT AND ORDER A FRESH REFERENCE RUN on the new master if anything comes back.**
A non-empty diff means the tree R1 measured is not the tree master now has, R1 is
not a reference on this master, and STEP 5's gate would be charged to this branch's
changes. Note that in this packet the ff makes HEAD the very commit R1 measured, so
the diff is empty by identity - which is why the proof is cheap here and why it
must still be printed rather than assumed.

    R1 IS NOW THE REFERENCE ON MASTER. Read back: HEAD = cbe9d05e7413..., tree
    b7a575217..., diff empty, rc 0.

### STEP 5 - run R2 on B's tree, gated against R1

    (tree checked out at 0355fe7b72c9497b12819c37d16795a66039c943)
    py -3 scripts/run_suite.py

EXPECT: completes; ZERO NEW NAMES against R1 (not against the `b1f290c84`
reference - that would charge this branch with landing 1's 6 paths).

ABORT: any new name, or a run that does not finish.

Ordering note: R2's measurement may be started before STEP 3, since B's tree exists
already. What STEP 4 gates is the *reuse decision*, not the measurement.

### STEP 6 - land B as a true merge

    git switch master
    git rev-parse HEAD          # ABORT unless cbe9d05e7413b0383d2329c3dc59d25d9f1205c9
    git merge 0355fe7b72c9497b12819c37d16795a66039c943

EXPECT: no conflict, a merge commit created, diffstat exactly `19 files changed,
2120 insertions(+), 12 deletions(-)` (constant 30 - what the merge brings on top of
its first parent). `merge.ff` is unset (constant 23) and the merge cannot
fast-forward anyway (constant 9), so a merge commit is the only outcome.

    git rev-parse HEAD^{tree}
    # 9fde760a6758dfba9522251f4d397ce0c4777f48      (constant 14 - THE readback)
    git rev-list --parents -n 1 HEAD
    # HEAD cbe9d05e7413b0383d2329c3dc59d25d9f1205c9 0355fe7b72c9497b12819c37d16795a66039c943
    git merge-base --is-ancestor cbe9d05e7413b0383d2329c3dc59d25d9f1205c9 HEAD   # rc 0
    git merge-base --is-ancestor 0355fe7b72c9497b12819c37d16795a66039c943 HEAD   # rc 0

The merge commit's own sha is **UNKNOWABLE in advance** and no packet can print it:
it is a function of author, committer, timestamp and message, not of content. Its
TREE is knowable and is the readback above.

ABORT: conflicts, or a tree other than `9fde760a...`. Nothing has been pushed, so
undo locally - `git merge --abort` if the merge is unmerged, otherwise `git reset
--hard cbe9d05e7413b0383d2329c3dc59d25d9f1205c9` - then re-measure
`git merge-tree --write-tree A B`; if it no longer returns `9fde760a...`, the packet
is VOID-PENDING.

### STEP 7 - push

    git push origin HEAD:refs/heads/master
    git rev-parse origin/master      # == HEAD
    git ls-remote origin refs/heads/master   # the same 40 hex

EXPECT rc 0 and `origin/master` equal to the new merge commit. The remote-side
expectation **was not recomputed by this task** (no network permitted): authority
`gh api repos/KatoKhan8/resonate-group-automation/rulesets`, and the recorded fact in
`_STANDING-RULES.md` that ruleset `master-protected` (id 25125359, Active,
`bypass_actors: []`) refused a push with GH013 on 2026-10-15 02:05. Read who refused
it (CLAUDE.md): a message naming the remote or a ruleset is a remote refusal - stop.
A message naming Claude Code's permission classifier is not a git refusal at all.

One push publishes both landings: landing 1's commit is an ancestor of this merge
commit. Pushing after landing 1 instead changes no number in this packet, only the
intermediate value of `origin/master` (which would then be `cbe9d05e7413...`).

## 5. ORDER 2 - `0355fe7b7` then `cbe9d05e7`

Identical to section 4 with the two branches swapped everywhere. The differences,
all measured:

    STEP 1  R1 = full suite on B's tree (0355fe7b72c9497b12819c37d16795a66039c943)
    STEP 2  gate R1 against the reference on b1f290c84: ZERO NEW NAMES
    STEP 3  git merge --ff-only 0355fe7b72c9497b12819c37d16795a66039c943
            EXPECT Fast-forward, diffstat `19 files changed, 2120 insertions(+),
            12 deletions(-)` (constant 29)
            readback  HEAD        = 0355fe7b72c9497b12819c37d16795a66039c943
                      HEAD^{tree} = 67c7a40f6c0397040f79a28e43590ba21c81b174 (constant 13)
    STEP 4  git diff HEAD 0355fe7b72c9497b12819c37d16795a66039c943
            EXPECT EMPTY, 0 bytes, rc 0 (constant 32); corroborate with
            merge-base --is-ancestor HEAD <B> rc 0.
            ABORT AND ORDER A FRESH REFERENCE RUN if anything comes back.
            R1 (B's run) IS NOW THE REFERENCE ON MASTER.
    STEP 5  R2 = suite on A's tree, gated against R1: ZERO NEW NAMES
    STEP 6  git merge cbe9d05e7413b0383d2329c3dc59d25d9f1205c9
            EXPECT no conflict, diffstat exactly `6 files changed, 2287
            insertions(+)` (constant 31)
            readback  HEAD^{tree} = 9fde760a6758dfba9522251f4d397ce0c4777f48
                      git rev-list --parents -n 1 HEAD
                      # HEAD 0355fe7b72c9497b12819c37d16795a66039c943 cbe9d05e7413...
                      both tips ancestors of HEAD, rc 0 each
            ABORT: conflicts, or a tree other than 9fde760a...; undo with
            `git merge --abort` / `git reset --hard 0355fe7b72c9497b12819c37d16795a66039c943`
    STEP 7  push as section 4; origin/master then equals the new merge commit

The composed tree is the same object in both orders (constant 14), and the
run accounting is the same: 2 runs, R1 sets the reference after landing 1, R2 is
not a reference on the final master either way.

## 6. Abort conditions, collected

| step | abort if | then |
|---|---|---|
| 0 | `origin/master` != `b1f290c84...`, or ls-remote disagrees, or a branch tip moved | packet VOID; nothing below applies |
| 1 / 5 | a run does not finish | no reference exists; the landing it gates does not proceed |
| 2 / 5-gate | any new name against the reference of record | branch does not land |
| 3 | `git rev-parse HEAD` != `b1f290c84...` before the ff | normalise local master (section 3 note 2), re-read |
| 3 | `merge --ff-only` refuses | stop; the ff precondition is gone; re-measure, do not substitute a merge commit |
| 3 | `HEAD^{tree}` != `b7a575217...` / `67c7a40f6...` | stop; packet VOID-PENDING |
| 4 | `git diff HEAD <branch>` prints anything | **order a fresh reference run on the new master**, do not reuse the branch log |
| 6 | conflicts | `git merge --abort`, re-measure merge-tree; if not `9fde760a...` rc 0, VOID-PENDING |
| 6 | `HEAD^{tree}` != `9fde760a...` | `git reset --hard <first-parent tip>` (nothing pushed yet) |
| 7 | push refused | read WHO refused it; a remote/ruleset refusal means stop |

## 7. A third landing - the note and the boundary

From `merge/0370`, recorded verbatim: **"A third landing would need +1 run, and one
run would serve it whichever order produced the composed tree."** This task's
measurements say why and when:

- the composed tree `9fde760a...` is the tree of **0 of 9866** commits in this
  repository (constant 21), and each branch's own tree is the tree of exactly 1
  commit (constant 22). So no run measured on the composed tree exists today - the
  +1 is a genuinely new reference.
- it can only be measured **after** landing 2 materialises the merge commit, because
  a suite run needs a checkout and no commit with that tree exists until then.
- it serves a third landing in **either** order, because the tree is one object
  either way (constant 14).

**Boundary, stated explicitly: this packet covers exactly two landings, the two SHAs
in step 0, and 2 runs. It does NOT cover a third.** If the operator adds the Track A
brake branch, `stop/0370`'s three-landing price governs and this packet does not
apply to it - the composed tree stops being the final state, and the reference this
packet leaves behind is not the one that landing needs.

One identity to confirm before the packet is executed, because the two documents
could otherwise be describing the same branch under two names: branch B here,
`0355fe7b72c9497b12819c37d16795a66039c943`, is `task-glm-c-0164-brake-ship`, and its
payload is brake-shaped - it adds `src/haltfile.py` and eight
`tests/test_the_stop_sending_brake_*` / `test_no_path_reaches_a_transport_...` files,
and edits `src/providerwrites.py`, `src/bisonfactory.py`, `scripts/resume_487.py`
(measured, constant 17). If `stop/0370`'s "Track A brake branch" is this branch, the
2-run price is not the three-landing question and the operator should reconcile the
two records before landing anything. **UNKNOWN to this lane**: `stop/0370`'s branch
identity, which would need its lane record.

## 8. UNKNOWN in this packet, with the authority each would need

| what | why not recomputed | authority needed |
|---|---|---|
| whether `origin/master` is still `b1f290c84` at landing time | no network in this lane; constant 1 is the tracking cache as last fetched | `git fetch` + `git ls-remote origin refs/heads/master` (step 0) |
| the reference run on `b1f290c84` (its existence, its tree flavour, its failing-name set) | its provenance is a suite log, and `_EXTERNAL-MODEL-RULES.md` section 7 forbids this lane `logs\*.out` | the reference log the gate consumes; the gate's own record |
| the per-branch GLM verdicts | a model call, with spend, not permitted here | `scripts/glm_verify_branch.py` per branch; CLAUDE.md requires it and FAIL / NEEDS_CLAUDE / UNKNOWN does not pass |
| the merge commit's sha | a function of author, committer, date and message, not of content | the operator's own commit, read back with `git rev-parse HEAD` |
| the remote's acceptance of the push | no network; and `gh api` is a network call | `gh api repos/KatoKhan8/resonate-group-automation/rulesets`; `_STANDING-RULES.md` records GH013 on 2026-10-15 |
| `stop/0370`'s Track A brake branch identity | outside this task's scope and its lane's records | `stop/0370`'s lane record |

## 9. What this task did not do

No merge, no cherry-pick, no push to master, no force-push, no ref moved. No
network, provider, campaign, send or activation call. No suite started and the
suite lock was not taken. Probes were `rev-parse`, `cat-file`, `merge-tree`,
`merge-base`, `for-each-ref`, `name-rev`, `rev-list`, `log --all --format`,
`diff`, `status`, `config --get` and `ls -l` - all read-only.
`git status --porcelain` was empty after every probe, and `HEAD` was
`0f48d5c4e86862fa6bf8c1d170b1c53edfb66ea5` at the close (stamp
2026-10-17T15:52:53Z).
