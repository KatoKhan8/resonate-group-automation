# Integration handoff — 2026-10-14

Lane closed. No merge, no master change, no remote deletion, no Slack message,
no sandbox run, no dispatch. `origin/master` is
`2bf7b8a571fe11bada4f56fbebeee768ab1e78a8` and was not touched.

Durable artefacts: `Desktop/resonate-ops/integration-2026-10-14/` (86 files,
17 MB, `MANIFEST.txt` lists every file with its size).

---

## 1. The push incident, and the general lesson

A Qwen worker I dispatched pushed its branch to the remote. Its brief forbade
pushing three separate times, in three different wordings. Its own summary says
"pushed to origin". Verified with `ls-remote`, not inferred.

**The lesson, stated generally: a brief cannot constrain a worker that shares
your credentials. Only the shape of the workspace can.**

My acceptance suite proved the *dispatcher* never pushes — a git shim recorded
all ten of its invocations and none was `push`, `checkout -B`, `reset --hard` or
a force, and the detector was proven able to fire on injected `push` and `-B`
lines. That was true and beside the point. I had put the worker in a **linked
worktree**, which shares the object store, the ref namespace, the configured
remote and the credential helper. The guard was written against the dispatcher
while the risk lived in the workspace.

Fix, implemented and proven: the workspace is now a standalone
`git clone --no-hardlinks` with **every remote removed**, and the dispatch
aborts if any remote survives. From such a clone,
`git push origin <branch>` exits 128 (`'origin' does not appear to be a git
repository`) and bare `git push` exits 128 (`No configured push destination`).

### Artefacts of the incident — KEPT, by operator decision

| ref | SHA | contents |
|---|---|---|
| `refs/heads/dispatch/s1/TASK-270` | `646e898a505caa2afd8d309a9573f6704eba26c2` | 3 files, +462: `src/revival.py`, one new test, the task file |
| `refs/heads/dispatch/s2/TASK-9801` | `878478d084aac36b5ae7bfb5e16a820e4a2a8c44` | one commit, "TASK-9801: claim", **0 insertions** — a TODO→RUNNING rename |

Neither is deleted. Deleting would be a second irreversible remote write to tidy
up, in the s2 case, nothing. `refs/heads/dispatch/s2/TASK-9802` does **not**
exist anywhere — that worker was stopped before it committed.

---

## 2. The dispatch gate: BLOCKED, measured

Removing the remote is not sufficient, because Git Credential Manager is
configured at **system** level and serves the token for any explicit
`https://github.com/...` URL. Four paired runs, all `--dry-run` against a ref
already at the identical SHA so nothing could be created:

| | configuration | exit | meaning |
|---|---|---|---|
| A | helper intact | **0** | credentials reachable by explicit URL |
| B1 | `credential.helper` cleared locally | **128** | the only effective config-level block |
| B2 | helper intact + `GIT_ASKPASS=/bin/false` | **0** | askpass alone blocks nothing |
| B3 | B1, then `git config --local --unset-all credential.helper` | **0** | one command restores access |

`IsInRole(Administrator)` is **False** and `New-NetFirewallRule` returns
**Access is denied**, so egress cannot be shaped to pass the Qwen endpoint and
block git. B1 is defeated per B3.

**Three routes would lift the gate**, each with the control that must go red:
an admin firewall rule on `git.exe`; a separate OS user or container with no
github.com entry in Windows Credential Manager; or a read-only token / branch
protection refusing `refs/heads/dispatch/*`. Detail in
`integration-2026-10-14/dispatch/DISPATCH-GATE-VERDICT.md`.

A design that removes the *reason* to commit task files to master —
`POOL_TASK_REF` separate from `POOL_BASE_REF`, with the exact lines to change
and six positive controls — is in
`integration-2026-10-14/dispatch/DESIGN-review-branch-dispatch.md`.
**Design only; not implemented.**

---

## 3. The backlog is results awaiting integration, not work awaiting doing

Of **261** task files in `TODO/` on master, **588** task ids already have a
finished (REVIEW/DONE) copy on some ref. After excluding those, the claimed and
the dependency-blocked, exactly **7** were dispatchable, and screening on the
tasks' own text left **1**. That is the shape of this backlog: the constraint is
review and integration, not worker capacity.

### Three counts, three criteria, deliberately not summed

| | count | criterion | purpose |
|---|---|---|---|
| **A** `claim_task.py --status` | **253** | a branch holds the file in a stage differing from master's, with a newer commit; **any** stage difference | do-not-dispatch |
| **B** `scan_backlog.py`, explicit master ref | **206** | file is REVIEW/DONE on some ref AND master's stage is not | integrable results |
| **C** only on `refs/preserve` | **29** | REVIEW/DONE on a pinned orphaned tip, on no remote ref | would be lost if the pins were dropped |

Overlaps by task id: A∩B **186** · A-only **67** · B-only **20** · C⊂A **21** ·
C∩B **0** (by construction) · C in neither **8**. Union **281**.

**The naive sum, 253+206+29 = 488, over-counts by 207.** The union is **not**
the canonical backlog and is not used as one: A and B answer different
questions, and ~6 of A's members are unexplained.

Why A exceeds B, measured over 1,015 refs: **48** of the 67 extras have no
REVIEW/DONE copy on any ref scanned; **2** are excluded by B because master is
already finished (TASK-560, TASK-911); **~6** (TASK-226/302/303/306/316/386)
show only TODO on branches with master also TODO, which A's documented criterion
does not explain — **UNRESOLVED**. An earlier namespace hypothesis of mine was
wrong: adding `refs/heads` moved B from 206 to 207.

`scripts/task173_scan.py` is **not trustworthy**: `text=True` decodes cp1250
here and three refs died with `UnicodeDecodeError` swallowed into an empty
string, and it reads the working tree as "master" — which is whatever branch is
checked out. It under-reports (216 vs 238 at the time) and it invented a result
for TASK-903 that does not exist.

---

## 4. Status of every claim: PASS / SELF-REPORTED / UNVERIFIED

### PASS — I ran it and it has a control that can fail

- **Clock scanner self-test.** `py -3 -m unittest
  tests.test_the_clock_scanner_can_see_what_it_certifies -v` → **12 tests, OK,
  exit 0** (read off the process), in my own worktree at `839803c64`. It carries
  its own negative controls by name, including
  `test_the_old_regex_instrument_reports_the_def_line` and
  `test_the_named_set_is_not_empty_control`.
- **Clock scan.** 44 rows over `src/`:
  `{unpatched 14, injectable 22, helper_body 4, module_level 2, indirect 2}`.
  Restricted to `SIMULATED_PATH_MODULES`: **2 rows, both injectable**
  (`senderheadroom.freshness`, `senderheadroom.earliest_day`) — the clock IS
  controllable on the simulated path. The two module-level reads
  (`src/demo.py:20`, `src/secondbrain.py:32`) sit outside it.
- **Safe-dispatcher contract**, 14 checks with paired negatives: task present →
  allowed; bad base ref → refused with 0 worktrees created; missing task →
  refused; own claim → refused; **foreign production claim → refused and that
  file byte-identical afterwards**; result in `refs/preserve` → refused, and
  allowed once removed (so not a tautology); existing branch → refused;
  existing path → refused; worktree reuse → refused; a refusal never logs
  `DISPATCHED`; a decoy worktree dirty three ways and holding a commit on no
  other ref came out with HEAD, branch ref, status hash and both files
  unchanged, with 10 git calls captured so the check was not vacuous; and that
  same dispatch still succeeded.
- **Recovery bundle.** 22 refs, complete history, `309bb0a7b7…`; all **29**
  orphaned results restored in a provably fresh bare repo (0 refs before fetch,
  no remote) and byte-identical by blob SHA-1; `sha256sum -c` 29/29 OK.
- **Clock-criteria preservation.** Four files committed here; each blob verified
  byte-identical to the agent worktree's copy, which stayed unmoved.

### SELF-REPORTED — the worker's word, not evidence

- **TASK-270.** The worker reported 6/6 new tests, 29/29 revival, 36/36
  reengagement lane, and 3 "pre-existing" `test_invariants` failures, exiting 0.
  **I ran none of it.** Its exit=0 and its six tests must not appear as
  confirmed anywhere. Parked; the operator is using the machine lock elsewhere.

  The command that would verify it later, from a clean checkout of
  `646e898a505caa2afd8d309a9573f6704eba26c2`:

      py -3 scripts/run_suite.py --offline -v
      # then diff failing NAMES both directions against a baseline measured on
      # 2bf7b8a57, per the standing rule that a baseline is a named list and is
      # compared by set, never by count

  Still missing after that: a positive control showing the six new tests can go
  red, and proof the three failures are pre-existing by name on the same commit.

### UNVERIFIED — known unknowns

- ~6 of `claim_task`'s 253 (above) — criterion unexplained.
- Content correctness of the 29 recovered results: saved, never reviewed.
- Whether the 300-account sandbox would pass: **NOT RUN**. C11 stays **HELD**.
- The actor behind the 1,352 orphaned reflog tips: the rewrite is proven
  against the remote, the mechanism is not. `pool.sh` writes worker logs with a
  truncating redirect, so each re-dispatch destroys the previous log.

---

## 5. My own two tests that were wrong first

These belong in the record because both were green or red for the wrong reason.

1. **C10 grepped the source** for `git push` and matched the worker brief's own
   `DO NOT PUSH. No 'git push'…` prose — testing the text of the source instead
   of the behaviour, exactly what this repo's rules warn against. Replaced with
   a git shim that records every invocation and asserts on what was *called*,
   plus two injected-line controls proving the detector can fire. A later
   iteration of the same check also flagged `worktree remove --force` on the
   dispatch's *own* clone; the pattern was narrowed and a scope assertion added
   that every removal target lies inside `SAFE_ROOT`.
2. **C12's shim sub-assertion was vacuous.** It asserted "no git call named the
   decoy" while the shim had recorded **0** invocations, so the clause could
   never fail. Fixed by requiring the captured-call count to be non-zero before
   the assertion counts; it then recorded 10. The first version of C12 was also
   wrong in a second way: it snapshotted all twelve live worker worktrees, two
   of which moved on their own mid-run (`resonate-qwen-3` edited by a live qwen,
   HEAD identical; `resonate-qwen-8` HEAD moved `fe39e0921`→`2bf7b8a57` by the
   production pool, status identical). Replaced by the decoy, which is isolated.

A third, for completeness: I authored a 300-accounts fixture task without first
checking `resonate-ops`, where a **300 accounts / 705 contacts** skeleton
already existed. Both versions of that task are now marked VOID. That is the
duplicate-dispatch failure I had spent the day guarding against.

---

## 6. Branches, SHAs, worktrees — and what is safe to delete

### Branches (local unless noted)

| branch | SHA | safe to delete? |
|---|---|---|
| `integ/clock-criteria-2026-10-14` | see §7 | **NO** — the only committed copy of the C11 criteria |
| `integ/safe-dispatch` | `a6cc5efd86f366aabf729736b83cdab1b5797dd7` | **NO** — the dispatcher and its contract |
| `integ/pool-base-ref` | `55c3c3ab0173154e89dd9e4dbe6eb4f15065f0c5` | **NO** — base-ref patch, 7/7 acceptance |
| `integ/verified-2026-10-12` | `a05ef5809a9e27a01f2ce72e1ba8078ca794eb72` | not yet — TASK-935, reviewed, unintegrated |
| `integ/candidates-2026-10-12` | `dab08367f6f40f0fba246f3b52038e5c79b4ccc3` | yes — TASK-977 parked, superseded by the above |
| `integ/dispatch-base-r94` | `f1df0b67a17a411d7cfde783ee80811025902a15` | yes — a dispatch base, reproducible |
| `integ/dispatch-base-s2` | `c328dc0e35f17b1bbe30dbe799e4636db8147604` | yes — same |
| `test/base-with-task`, `test/safe-base` | `b0386e225e…`, `58a8ffdd16…` | yes — test fixtures |
| `dispatch/s1/TASK-270` *(also remote)* | `646e898a50…` | **NO** — self-reported result, kept per decision |
| `dispatch/s2/TASK-9801` *(also remote)* | `878478d084…` | **NO** — kept per decision |
| `refs/preserve/*` — **1,352 refs** | — | **NO** — 29 results exist only here |

### Worktrees — all mine, all safe to remove

`wt-inv`, `wt-pool`, `wt-integ`, `wt-verify`, `wt-safe`, `wt-clock`, `wt-crit`
under the session scratchpad; `safe-tb/{main,w/testworker,w/hog}`, `dispclone2`;
and the three dispatch workspaces `dispatch/wt/{s1-TASK-270, s2-TASK-9801,
s2-TASK-9802}`. Nothing in them is unique — every branch they carry is listed
above and every artefact is in `integration-2026-10-14/`.

**NOT mine, do not touch:** the twelve `Desktop/resonate-qwen-*` worktrees (10
of 12 carry tracked changes; 45 commits ahead of their own branches, all four
carriers reachable from dedicated remote branches) and
`.claude/worktrees/agent-aa270fe8a9148e85c`.

---

## 7. Decision documents that live outside git

**`Desktop/resonate-ops` is not a git repository.** 13,302 files, 388 MB, no
`.git`, no sibling backup found. It holds the operator-facing decision record:

| file | size | why it matters |
|---|---|---|
| `PREREG-C11-wall-clock-2026-10-13.md` | 9,549 B | **the** pre-registration; fixes the criterion before any further run |
| `C11c-DISPOSITIONS-2026-10-13.md` | 25,659 B | C11c dispositions |
| `C11c-SET-DRIFT-AND-SPENDLEDGER-REPRO-2026-10-13.md` | 18,023 B | set drift + repro |
| `c11d-2026-10-14/C11D-OPTION-D.json` | 1,477 B | C11d |
| `c11e-2026-10-14/C11E-REPORT.json` | 9,015 B | C11e |
| `DECISIONS-OPEN-2026-10-13.md` | — | open operator decisions |
| `campaign-skeleton-2026-10-13/SKELETON-300x700.md` | 44,135 B | 300 accounts / 705 contacts skeleton, batch01 generated |
| `BRIEF-OPTOUT-AND-SANDBOX-2026-10-12.md` | 15,597 B | standing brief |
| `batch01-readiness-2026-10-14/` | 176 KB | batch-01 readiness |

**Correction to what I reported yesterday.** I said C11c/C11d/C11e were "not
locatable in any ref". True of git — and I had not looked in `resonate-ops`,
where they exist as documents. They are **un-versioned, not lost**.

**At risk:** all of it, equally, for the same reason the clock scanner was — one
disk, no version control, no backup. The clock scanner was the acute case
because it was *also* untracked inside a worktree that could be pruned; these
files at least sit in a stable directory. Nothing here was moved or modified by
me. Putting `resonate-ops` under git, or a scheduled copy off this machine, is
the single highest-value durability action left and it is an operator decision.

---

## 8. Open claims left in place

My own isolated ledger at `integration-2026-10-14/../dispatch/claims` holds
`TASK-270`, `TASK-9801`, `TASK-9802`. Left deliberately: while the push incident
is open they block re-dispatch of those three ids. They are in my own ledger,
not the shared one.

The production ledger (`work/claims`) held `TASK-978` and `TASK-993` at close. I
never wrote to it, and released nothing from it.

## 9. Also recorded, not my lane

`.claude/worktrees/agent-aa270fe8a9148e85c` (branch
`task-sandbox-run-2026-10-12`, HEAD `839803c64`) keeps producing files that are
committed nowhere. It had two untracked files when I first looked and four an
hour later. Four are now preserved and committed on
`integ/clock-criteria-2026-10-14`; whoever owns that agent should know it is
accumulating work outside git.
