# CANARY/0170 - the src/suitelock.py blob lineage and the L323 landing order

Measured 2026-10-17 by TASK canary/0170, read-only, standing in the worktree
C:\Users\Zvonimir\Desktop\resonate-trees\wt-canary-2026-10-16 on branch
task-canary-0140-l323-test-2026-10-17 at HEAD 7fbf1078c5f6eb417255ec8d84c6f3967bda8eaf.
origin/master was b1f290c847eb2500b7eb39987ac34f6d6a8d00d2 at open AND at close
(ls-remote and the local tracking ref agree, both reads). No ref moved, no
checkout, no fetch, no suite run, no lock taken. Scratch instruments and logs:
C:\Users\Zvonimir\Desktop\resonate-ops\task-canary-0170-scratch\ (census.py,
arms.py, compose.py, scan_orphans.py, census_results.json,
arms_results.json, compose_results.json, per-arm logs under arms\).

## The one question, answered

11 distinct src/suitelock.py blobs are reachable from any ref of this
repository. Denominator: `git rev-list --all --full-history -- src/suitelock.py`
walks the 2,530 refs of `git for-each-ref` (622 heads, 1352 preserve,
547 remotes, 5 tags, 1 stash, 1 notes, 1 local, 1 recovered) plus HEAD plus
the per-worktree HEADs of the 316 registered worktrees, which for-each-ref
does NOT list and for-each-ref --contains does NOT check - two of the 35
path-touching commits (42179354e, 852bb5eef) are reachable ONLY that way
(proven by git log --all --source: worktrees/wt-merged/HEAD and
worktrees/wt-pilotcaps-0232-c1/HEAD). 362 of the 2,530 refs hold a suitelock
blob at tip; every tip blob is also in the history walk (cross-checked).

Classes: 9 ZERO, 1 PARTIAL, 1 FULL. The L323 test
(tests/test_a_holder_that_dies_mid_check_is_stale_not_held.py, blob
486b9b3398e30448b5b34dc6be44fe38a6fb551c, added by 7fbf1078c) is GREEN
against exactly one blob, FULL ea0dbdd8, and RED against the other ten.
The landing is ORDERABLE; the table is at the end.

## Classifier

Structural, ast-based (raw token counts are inadmissible: 430891fc contains
the substring HELD ten times via the bookkeeping global _HELD_LOCK_PATH and
STALE once via docstring prose, while holding no verdict vocabulary at all).
Vocabulary present iff the module top level has `def holder_state`,
`def process_identity`, or a constant assignment named exactly HELD, STALE or
UNIDENTIFIABLE. FULL iff UNIDENTIFIABLE is present (the brief's definition);
PARTIAL iff some vocabulary without UNIDENTIFIABLE; ZERO iff none;
UNPARSEABLE reported, never bucketed.

Positive controls, printed and PASSING before the census was trusted:
12de2433 -> ZERO (master's blob; the 0140 red arm measured no vocabulary and
a _takeable-derived 'held'), ea0dbdd8 -> FULL (the 0140 green arm),
430891fc -> ZERO (this branch's own base, TASK 0090). 3/3 PASS.
The population itself contains all three classes, so the synthetic-arm
contingency in the brief did not trigger; the classifier printed ZERO nine
times, PARTIAL once (274985b9) and FULL once (ea0dbdd8) on real blobs.

## The census

Blob (full oid) | size | class | at tip of | reachable from | introduced by
--- | --- | --- | --- | --- | ---
0bc344dcb4f5670569b2c51d23cf83eaa9f32557 | 8199 | ZERO | 1 ref (heads/task-suite-lock) | 362 refs | 7e6f53676 2026-10-02 "One full suite at a time..." (first suitelock; 8 holder commits incl. 42179354e which only wt-merged/HEAD reaches)
12de2433e6555a92a7def2cf5d2b5da7c2547c8c | 22013 | ZERO | 288 refs (incl. heads/master and origin/master b1f290c84) | 360 refs | c789d270d 2026-10-02 "started_at said when the run launched..." (9 holder commits, latest 5d6d1cebc 2026-10-03)
274985b97cd96330cda158153f9156f78939b087 | 37950 | PARTIAL | 2 refs (heads + origin/task-suppression-0300-differ-failclosed-2026-10-16) | 2 refs | 79e1878e8 2026-10-16 16:58 "TASK-0399: the lock holder was a PID..." - a COMPETING 0399 implementation: holder_state(file_path, holder) transposed signature, HELD="HELD"/STALE="STALE" uppercase strings, _pid_identity (no process_identity), no UNIDENTIFIABLE
430891fc65163eba9451c13fa83fdb5db35e6742 | 28381 | ZERO | 4 refs (heads+origin of task-canary-0090-release-fix-2026-10-16 and task-canary-0140-l323-test-2026-10-17) | 4 refs | b5df96f3a 2026-10-17 00:37 "TASK 0090: a completed run never leaves the suite lock behind"
4c63d40d41ed2a8b20c3321f5d5a3030a7638363 | 35300 | ZERO | 1 ref (origin/task-qwen-0090-watcher-treekill-2026-10-15) | 1 ref | 119d54596 "TASK 0170, RECOVERED BY 0171" - a DIFFERENT lane's task 0170, numbering collision only
63f079295a283ac05a96e1a8ca180be28f3395bd | 26778 | ZERO | 61 refs (pilotcaps/integ/gates/glm/deepseek lineages) + refs/stash tip state | 61 refs | 4d2d19b9b 2026-10-14 "suitelock: an unreadable process table is UNKNOWN, never DEAD" (10 holder commits incl. stash fcf02d7e6 and 852bb5eef which only wt-pilotcaps-0232-c1/HEAD reaches)
8816fe4e3f60ce52ac210efb3b8846c6e0de0769 | 20519 | ZERO | 0 refs | 360 refs | a7c81b896 2026-10-02 "The starvation this branch predicted happened..."
bc46a8ffd939dc970151348b2abe6a34b85af2dc | 16421 | ZERO | 1 ref (heads/task-lock-fifo-and-label) | 361 refs | 338d62722 2026-10-02 "The queue is first come first served..."
da13c5be0899e17bc27bfa65e0f30736cf8e3280 | 19710 | ZERO | 0 refs | 360 refs | 29089214e 2026-10-02 "A live holder's lock is never taken..."
ea0dbdd872bd3a02732ade7fd5f89ba9064b486c | 34353 | FULL | 2 refs: heads/task-suppression-0399-lock-identity-2026-10-16 AND origin/same (named explicitly: this is the "with 0399" anchor) | 2 refs | c85724df0 2026-10-16 15:10 "TASK 0399: the suite lock's holder is a process, not a number" (the branch's only commit over master)
eb169c2580270459494795dace1d3102dfcbfff3 | 31344 | ZERO | 2 refs (heads + origin/task-deepseek-0020-lock-identity-2026-10-16) | 2 refs | 76987af67 2026-10-16 17:00 "The lock's holder is a pid AND a start time" - a THIRD identity approach (_proc_start/_holder_alive/_identity_note, no holder_state)

## Red vs green, measured not predicted

Every one of the 11 blobs ran the L323 test module-scoped in a hermetic
scratch package (arms.py; the test uses only explicit temp file_path values,
path() is never invoked, the live machine lock is never read or stat'd; pyc
swept after every .py write per the bytecode rule - the sweep counter fired
on 10 of 11 arms, the first arm had no cache yet):

- GREEN (1): ea0dbdd8 - Ran 2 tests, OK, rc=0. holder_state reaches the GONE
  branch, return at L323 of that blob, "stronger witness" reason, STALE,
  _takeable True.
- RED (10), in three flavours:
  - assertion, observed 'held' (planted _alive=True consulted directly):
    12de2433 (master), 430891fc (this branch's base), 4c63d40d, 8816fe4e,
    da13c5be, eb169c25.
  - assertion at the witness phrase, observed 'stale': 63f07929 - its
    _takeable(file_path, holder, runner=None) consults _probe(pid, runner),
    NOT _alive, so the plant misses the decision path, the real table read
    finds the synthetic pid dead and the derived verdict is 'stale' without
    the GONE-branch reason.
  - errors, missing API: 0bc344dc and bc46a8ff (AttributeError: no
    _takeable - pre-takeable generations); 274985b9 (2 errors: the
    transposed holder_state(file_path, holder) signature receives the holder
    dict as file_path - 'str' object has no attribute 'get' - and the plants
    test asserts process_identity which that blob does not define).

So the red/green blob PAIR the question asks for: (486b9b33, ea0dbdd8) is
green; (486b9b33, 12de2433) is the master red arm; (486b9b33, 430891fc) is
this branch's own born-red state. "L323" is an ea0dbdd8 line identity: in
the composed blob below the same return sits at L348.

## The composition probe (the part nobody had measured)

0399 and 0140 both edit src/suitelock.py from the same base 12de2433, and
old-mode merge-tree (writes no objects) showed ZERO conflict markers. Reproduced
deterministically with `git merge-file -p` in scratch:

- ea0dbdd8 (ours) + 12de2433 (base) + 430891fc (theirs): rc=0, 0 conflict
  markers, 40721 bytes, class FULL, contains BOTH mechanisms
  (_HELD_LOCK_PATH x8 from 0090, holder_state/process_identity/
  UNIDENTIFIABLE x12 from 0399). Predicted blob oid if landed byte-identical
  in LF: 4f735245a1a3cdf0f994ec8d340beb959b69e64c (computed with hash-object
  WITHOUT -w; nothing written to the odb).
- L323 test vs the composed blob: GREEN, Ran 2 tests, OK.
- 0399's own collateral tests/test_the_suite_lock_holder_is_a_process_not_a_number.py
  (26 tests) vs the composed blob: GREEN, Ran 26 tests, OK, 32.5s (hermetic:
  ast-checked imports = stdlib + src only; grep proved it never calls
  suitelock.path()).
- 0090's collateral tests/test_one_full_suite_at_a_time.py: NOT RUN - it
  calls suitelock.path(), the LIVE machine-lock resolver (lines 30/45/51),
  and this brief forbids taking the suite lock. That is the one green-on-
  composed claim this report does NOT make; the landing run must cover it.
- ea0dbdd8 + base + 274985b9 (competing 0399): 8 conflict markers,
  UNPARSEABLE. The two TASK-0399 implementations do not compose.
- ea0dbdd8 + base + eb169c25 (deepseek-0020): 5 conflict markers,
  UNPARSEABLE.
- ea0dbdd8 carries ZERO _HELD_LOCK_PATH hits: landing 0399 alone does not
  bring 0090's release fix, and b5df96f3a is NOT an ancestor of c85724df0
  (merge-base --is-ancestor measured). The composed blob, not either parent,
  is the state that holds both guarantees.

## The landing-order table

Ancestry measured at open: master b1f290c847eb2500b7eb39987ac34f6d6a8d00d2
is an ANCESTOR of both 0399's tip c85724df0ef4d3f477bcc283a79a208f9d40466a
and 0140's tip 7fbf1078c5f6eb417255ec8d84c6f3967bda8eaf; c85724df0 is NOT an
ancestor of 7fbf1078c; merge-base of the two is b1f290c84 itself. Both
branches are one-merge units over master.

Order | Unit | Depends-on | L323 state where it lands
--- | --- | --- | ---
1 | task-suppression-0399-lock-identity-2026-10-16 @ c85724df0 (suitelock ea0dbdd8, FULL) | master b1f290c84 only; fast-forwardable (ANCESTOR measured) | test absent; master's suitelock becomes FULL
2 | task-canary-0140-l323-test-2026-10-17 @ 7fbf1078c (test 486b9b33 + 0090's suitelock edit 430891fc) | unit 1 MUST be on master first OR in the same batch, merged second | GREEN - measured on the auto-composed blob (0 conflicts, FULL, 2/2 OK, collateral 26/26 OK). The merge composes src/suitelock.py into the NEW 12th blob (predicted 4f735245 in LF); per the operator's standing rule any src/ change still needs a fresh full-suite reference before the gate certifies - module-scoped green is not that reference.
never-as-is | task-suppression-0300-differ-failclosed-2026-10-16 @ 79e1878e8 (suitelock 274985b9, PARTIAL) | conflicts with unit 1: 8 markers, UNPARSEABLE | RED (2 errors) wherever it lands, and it cannot auto-compose with ea0dbdd8. Its other 42 commits are suppression work unaffected by this; if it must land, its suitelock has to be resolved to a FULL composition by hand or 79e1878e8 dropped/rebased off - an operator decision, recorded not implemented.
never-as-is | task-deepseek-0020-lock-identity-2026-10-16 @ 76987af67 (suitelock eb169c25, ZERO) | conflicts with unit 1: 5 markers, UNPARSEABLE | RED ('held'); same hand-resolution requirement.

Reverse order (0140 before 0399) is gate-blocked and red: master would carry
the test against 430891fc - measured RED, observed 'held' - one new failing
name against any zero-new-names reference. Units 1 and 2 may share one batch;
the only hard constraint is that 0399's suitelock change and the test meet in
a tree whose src/suitelock.py classifies FULL - verify with the ast
classifier at landing, never by eye.

Verdict: ORDERABLE. Nothing is missing from the repository to answer; the
one unrun check (0090's collateral test) is named above with the authority
needed (a run permitted to touch the live lock resolver, i.e. the landing
lane's own suite run).

## Anomalies and findings for the record

1. `git for-each-ref` undercounts what `rev-list --all` walks: linked
   worktrees' HEADs (316 worktrees registered) are in --all but not in
   for-each-ref, and --contains does not test them. Any census that equates
   the two misattributes. Here it changed no class and no count (both orphan
   commits' blobs are reachable from ordinary refs through other holder
   commits) but it would silently shrink a denominator in another census.
2. THREE parallel lock-identity implementations coexist on three branches
   (0399-identity FULL, 0300-differ PARTIAL, deepseek-0020 ZERO) and only
   the first greens the L323 test; the other two do not auto-merge with it.
   Whichever lands second needs a human resolution. Operator decision.
3. refs/stash (fcf02d7e6, "On task-pool-0120...") holds a suitelock edit
   (63f07929) in its working-tree state - a stash is part of the blob
   population and of every --all walk.
4. The 63f07929 generation moved the liveness seam from _alive to
   _probe(pid, runner): a test that plants _alive silently misses the
   decision path on that blob. Plants must be witnessed against the seam
   the blob actually consults - this test's witness test passes there while
   the verdict test fails at the reason phrase, which is exactly how a
   bypassed plant should look.
