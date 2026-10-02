# Morning handover, 2026-10-03

**Written during the night and filled in as it went**, in the order the operator
asked for it. A section that says PENDING has not happened yet; a section that
says BLOCKED says what is blocking it and who can unblock it.

---

## 1. Master SHA

**`cd8e00bc`** as of 01:40. Thirty commits ahead of `origin/master`
(`10a38310`); **nothing pushed** — the push is still the operator's decision.

The night's merge: **`ae134dd2`** (TASK-940 at `b3ac5c34`), then **`cd8e00bc`**
(`scripts/ops`). Both with `git diff master <branch>` proven empty where the
one-run shortcut was used.

## 2. The merges, with their GLM verdicts

| branch | head | suite | GLM | outcome |
|---|---|---|---|---|
| `task-940-glm-verifier` | `b3ac5c34` | 230 names, 0 new, 1 gone (A44) | **PASS** | **MERGED** at `ae134dd2` |
| `task-one-os-authority` | `3411e085` | 231/0/0 then stale | **FAIL**, 8 parts | **not merged** — A45, see §5 |
| `task-word-contract-enforced` | `e62b0bc2` | **231/0/0 clean**, twice | **FAIL** twice: 1=PASS 2=PASS 3=FAIL on the second | **not merged** — one real finding left, §5 |
| `task-942-token-budget` | `b82304ab` | **run in flight** from 01:48:46 | PENDING — it has its own task file | PENDING |
| guard / 936 / the five older bases | — | — | — | PENDING |

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
6. **The push.** Thirty commits.

## 7. Queue, Qwen and GLM numbers

- **Qwen: did not run.** Operator's standing order, unchanged all night.
- **GLM: 19 calls tonight**, all attributed — TASK-940 ×6, TASK-962 ×8 (the
  first multi-part review), TASK-968 ×3 + the re-run in flight, TASK-959 ×0.
  Production ledger: **64 glm rows, 986,737 µUSD** after the migration, up from
  41 rows before it.
- **Suite runs: 7** — one killed deliberately (a tree that had to change), one
  unusable (the contaminated reference), one re-measured reference, and four
  gate runs.
- **Task files opened tonight:** 959, 960, 961, 962, 963, 964, 965, 966, 967,
  968, 969.
