# Morning handover, 2026-10-03

**Written during the night and filled in as it went**, in the order the operator
asked for it. A section that says PENDING has not happened yet; a section that
says BLOCKED says what is blocking it and who can unblock it.

---

## 1. Master SHA

**`e967271d`** as of 06:20, unchanged since 04:10 — **the guard branch did not
merge**, so no merge landed after it. **Master is still unpushed**: the push is
the operator's decision. The night's FINDINGS are pushed, though —
`task-defect-map` is on the remote at **`d03fce07`**, verified against
`origin/task-defect-map`, so nothing below exists only in this terminal.

The night's merges, in order: **`ae134dd2`** (TASK-940 at `b3ac5c34`),
**`cd8e00bc`** (`scripts/ops`), **`0c9adf0a`** (TASK-942 at `b82304ab`) and
**`e967271d`** (942's verdict as a file). Each merge was of the MEASURED commit and
`git diff master <branch>` was proven EMPTY afterwards, so each gate run became
master's next reference.

## 2. The merges, with their GLM verdicts

| branch | head | suite | GLM | outcome |
|---|---|---|---|---|
| `task-940-glm-verifier` | `b3ac5c34` | 230 names, 0 new, 1 gone (A44) | **PASS** | **MERGED** at `ae134dd2` |
| `task-one-os-authority` | `3411e085` | 231/0/0 then stale | **FAIL**, 8 parts | **not merged** — A45, see §5 |
| `task-word-contract-enforced` | `e62b0bc2` | **231/0/0 clean**, twice | **FAIL** twice: 1=PASS 2=PASS 3=FAIL on the second | **not merged** — one real finding left, §5 |
| `task-942-token-budget` | `b82304ab` | **231/0/0 on run 2**; run 1's seven were the tests' own (TASK-970) | **PASS**, 3 parts, at the third attempt — the first two failed on the GATE, not the branch | **MERGED** at `0c9adf0a` |
| `task-guard-regressions-rebased` | `eff4e890` | **231/0/0 CLEAN**, first run, 2,099.5s, 14,759 results, against `reference-231-master-0c9adf0a.log` | **FAIL**, 5 parts: 1=PASS 2=FAIL 3=PASS 4=FAIL 5=NEEDS_CLAUDE | **not merged.** Still REQUIRED for the canary — the internal-campaign protection exists nowhere on master (`hasattr(providerwrites, "classify_campaign")` is False there). **Two of the three refusals are the gate's and one is a stale file the branch ships; its CODE measured clean.** See §5 A46–A48 and the decision in §6 |
| 936 / the five older bases | — | — | — | PENDING |

**The guard branch's verdict is the clearest case of the night that a gate
verdict is evidence about the gate as much as about the branch.** Part 2's stated
mechanism was REFUTED by measurement, part 4's first claim named a failure that
is in the reference, part 5 could not read a file that parses whole, and what
remained after checking all three was one real defect in `src/store.py` that
nobody had been looking for. Written up as A46–A48 rather than argued away.

**The GLM gate itself was repaired twice tonight** — see §5 — and the queue's
verdicts are only as good as the tool that produced them, which is why each FAIL
below was verified in the source before it was accepted.

## 3. Phase 0 / phase 1

**PENDING, and still behind the merges, as ordered.** Phase 2 was redefined as a
90-day simulation (`resonate-ops/briefs/phase2-brief.md`) and still runs after
0 and 1.

## 4. Before/after copy for bigfish and savagebrands

**BLOCKED, deliberately, and the blockers are named.**

- **before** for bigfish exists and is measured:
  `resonate-ops/copy-review/FINDING-bigfish-2026-10-02.md` — the operator's
  *"passes the gates, would not be sent"* with five measured reasons.
- **after** needs TASK-964's rules in code. They are not written yet; its four
  acceptance commands fail today with `AttributeError` by design.
- **savagebrands** is not generated until TASK-964 is in — operator's
  instruction, and the reason is the finding above: generating against today's
  gates produces more of the same.
- Expect **em1 HELD `research_required`** and **em3 HELD `proof_required`** on
  both when it does run. That is the correct outcome and a finding for the
  client, not a defect.

## 5. Open defects

| id | what | state |
|---|---|---|
| **A44 / TASK-963** | a send guard switched off by the DIRECTORY NAME — `any(a in p for a in allowed)` over an absolute path, so a worktree called `glm-940` exempted every file | OPEN. Cost tonight: one unusable verdict, one re-measured reference. The naming rule is in `resonate-ops/README.md` |
| **A45 / TASK-967** | the prior-contact authority ships UNCALLED — `generate.py` still passes `bool(claims.prior_contact(...))` and `may_claim_first_contact` has zero callers. The real fix wires the dossier into the copy path, which is a provider read per contact | OPEN, needs the operator's decision on cost/caching |
| **A45(b)** | `canary_cohort.py` said "EXACTLY 43 rows - and 52 of them are the wrong people" | FIXED on the branch, re-measured: the predicate still selects exactly 43 |
| **A41 / TASK-960** | the spend ledger resolves per worktree for every caller | DATA MIGRATED (20 rows, 262,114 µUSD, idempotent). CODE still open for callers other than the verifier |
| **TASK-969** | the verifier ran test files the branch had DELETED and failed the branch for it | fixed in the tool the queue runs (`413a9682`); OPEN until it lands on master |
| **TASK-961** | `_merge_commit_for` takes the oldest ancestry-path merge; `_find_task_file` leaks its temp copy | OPEN |
| **TASK-959** | `--timeout` is inert above the adapter's 180s clamp; the prompt-size measurement | OPEN (the multi-part design is DONE and in use) |
| **A21** | three of bigfish's five steps are below the writer contract while `lint` reported zero failures | the enforcement is what 943 would merge; the NUMBERS are TASK-964 |
| **A46 / TASK-973** | **the production-write barrier protects the wrong `work/`.** `refuse_production_write` refuses `ROOT/work` of the tree it was imported from; every gate suite runs from a worktree, so the main checkout's `work/campaigns.jsonl` — the OS authority — has been outside the barrier for every run that ever gated a merge. Measured under `unittest`: this tree REFUSED, main checkout ALLOWED | OPEN, and the one to fix first. The estate is intact (117,823 bytes, 69 rows, mtime 2026-09-30) because `use_directory` pops `CAMPAIGNS` for every `ProviderTest` — the layer nobody advertised as the barrier. Fix is the one CLAUDE.md already names: `--git-common-dir` |
| **A47 / TASK-974** | the guard branch commits `SUITE-task-guard-regressions-2026-10-02.json` attesting `31bc1801`, which `merge-base --is-ancestor` says is **not even an ancestor** of `eff4e890`. It is what sent two of the five GLM parts off the rails | OPEN. Cheap: regenerate from a run of the commit it ships with, or delete it. **Do not hand-edit the `commit` field.** The structural half is a test that reds when a committed attestation names a non-ancestor |
| **A48 / TASK-975** | **the FOURTH gate defect tonight.** `patch_parts` gives an oversized file its own part and calls it a mid-file cut in its own docstring, while `part_sentence` tells every call "every file is shown COMPLETE in exactly one part — not NEEDS_CLAUDE". Reproduced at 28,107 chars over a 5,000 room; GLM reported 28,863 of 51,319 | OPEN. The fix with leverage is to keep generated `docs/state/*.json` out of the prompt budget entirely — it is evidence, not code |
| **943's keyless doors** | `approve`, `eligibility`, `executionguard` and `campaigns` call `lint.check` with NO step key, and the contract reaches them only through `step_key_of`. The DELETED 295-line test was the only place that path was driven | OPEN — one test per door, or one end-to-end, with the `step_key_of`-returns-None mutation as proof. Recorded in TASK-968 |

## 6. Decisions for the operator

1. **The 16 em1 exemplars and the Volteum cadence.** Neither is reachable from
   this machine: EmailBison exposes no sent-message body endpoint, and no
   campaign in the workspace is named Volteum (40 listed, real names printed
   beside the empty hit). Supply the content, or authorise a new provider read.
2. **Three word contracts exist.** The operator's new one (em1 90–140, target
   120), the standing writer contract (em1–em3 60–90) and `WORD_CONTRACT` as
   943 enforces it (em1 ceiling **90**). **A 120-word em1 would be REFUSED on
   the merged master** — the two intersect at one value. TASK-964 must set
   `em1: (90,120,140)`; confirm that is the intent.
3. **Their own em1s are twice the new contract**: the five internal campaigns'
   order-1 steps measure 261, 281, 279, 246 and 72 words.
4. **"Unknown calls nothing"** (order C) contradicts a deliberate safety
   reduction — the stop is attempted BEFORE classification because it can only
   mean somebody receives less. Confirm with that consequence stated, or drop
   it. The notification half is genuinely missing (A8/TASK-941).
5. **TASK-967's cost**: wiring the dossier means a provider read per contact
   inside the generation loop. Decide caching and what an unreadable dossier
   does to generation volume before it is enforced.
6. **The guard branch, and it is the one worth your attention.** Its code
   measured CLEAN (231/231, 0 new) and it is required for the canary, but its
   gate verdict is FAIL and NEEDS_CLAUDE does not pass — your rule, and I have
   not overruled it at 06:00 on my own say-so. Of the three refusals: part 2's
   mechanism is refuted, part 5's is a gate defect (A48), and part 4's is real
   but is a stale JSON the branch ships (A47), fixable in minutes. **The honest
   path is: fix A47 on the branch, fix A48 in the gate, re-run the review —
   no new suite needed, the tree does not change for A47 beyond one generated
   file** — and that is a decision about sequencing, so it is yours. The
   alternative you may prefer: merge on the measured suite plus a re-run after
   A47, treating A48 as a gate task.
7. **The push.** Thirty commits on master, still unpushed. The findings branch
   is pushed and verified.

## 7. Queue, Qwen and GLM numbers

- **Qwen: did not run.** Operator's standing order, unchanged all night.
- **GLM calls MADE tonight: 28**, 619,067 µUSD — TASK-940 ×2, TASK-942 ×7, TASK-962 ×8, TASK-968 ×6, TASK-972 ×5 (the guard branch's five parts, 99,883 µUSD). Every one attributed to a task.
- **Rows MIGRATED into the ledger tonight: 20** (262,114 µUSD) — earlier
  calls that had been billed into worktree ledgers, not new spend.
- **Suite runs: 10** — one killed deliberately (a tree that had to change), one
  unusable (the contaminated reference), one re-measured reference, and seven
  gate runs, two of which were second attempts on the same tree (943 after its
  findings were fixed, 942 after seven order-dependent names).
- **Suite runs: the tenth and last was the guard branch's**, finished clean at
  05:03 (2,099.5s) — the only branch tonight whose first gate run was clean.
- **Task files opened tonight: 959 through 975.** **Four of them — 963, 969,
  971 and 975 — are defects in the GATE rather than in any branch**, and all
  four were measured after a branch was wrongly refused. None has landed on
  master yet, because each must pass through the gate it fixes.
- **TASK-972** (the guard branch's own task file, written after the code and
  saying so) is committed on the branch at `eff4e890`; its three acceptance
  commands pass there and command 1 fails on master with "there is no ownership
  classifier - this is master, not the branch".
