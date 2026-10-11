# Integration queue - 2026-10-12

Triage of the task pool's integration backlog. Produced by a time-boxed lane with no merge rights.

## Counts

| | |
|---|---|
| Awaiting integration (claim_task.py --status) | 245 |
| Integrated by this lane | 0 (by design - the operator reserves merges, and the merge gate wants a full suite) |
| Queued for integration (passed every check) | 147 |
| Distinct branches those 147 tasks sit on | 61 |
| Parked (failed at least one check) | 98 |
| Released | 0 (TASK-978 was released by the operator before this lane started) |

## Which tool the dispatcher believes

`scripts/claim_task.py` is the authority: `scripts/pool.sh` calls it and nothing else - `busy()` and `next_ready()` both shell out to `claim_task.py --status`, and `dispatch()` claims through `claim_task.py --claim`. `scripts/pool_dispatch.sh` sources `pool.sh` and reuses that same `dispatch()`, so there is one claim path, not two.

`scripts/task_registry.py` is never invoked by either script (`grep task_registry scripts/pool*.sh` is empty). Its READY 257 is a directory census - every file in `TODO/` - while claim_task's ready 1 additionally subtracts the 245 tasks whose result already exists on a branch and the held claims. Both numbers are correct about different questions; only claim_task's governs what a worker is handed.

## The acceptance check, exactly as applied

A task is QUEUED only if all five hold. Anything else is PARKED with one line and no investigation.

1. the branch carrying the result still exists (local or origin);
2. `git diff master...<branch>` is non-empty;
3. that diff does not delete more than 300 lines net;
4. that diff touches no file under `work/` or `config/`;
5. the stage on the branch is DONE or AWAITING_REVIEW (not BLOCKED, not REWORK), and the task file header carries no `STATUS: BLOCKED` / `STATUS: REWORK`.

Nothing more expensive was run: no suite, no merge, no rebase, no per-task diff reading.

## Read this before working the queue

**A branch is not a task.** The 245 results sit on 74 refs and the 147 queued tasks sit on 61 branches - one branch carries 29 of them. The rank below is per-task but the diff measured is the *branch's*, so every task sharing a branch shares a rank band and integrating one integrates its siblings. Work the queue top-down by branch: the first ~20 entries are single-task branches, which are the cheapest and safest merges available.

No branch in the whole 245 had an empty diff, and none deleted more than 300 lines net (worst case is 0 net deletion), so checks 2 and 3 eliminated nobody. The parked set is entirely check 1, check 4 and check 5.

## Ranked queue (smallest branch diff first)

| # | task | branch | where | stage | branch diff | files | tasks on this branch | justification |
|---|---|---|---|---|---|---|---|---|
| 1 | TASK-977 | `task-977-five-master-failures` | local+origin | AWAITING_REVIEW | +91/-25 | 5 | 1 | result exists on a live branch, 116-line diff over 5 files, no work/ or config/, no net deletion, stage AWAITING_REVIEW |
| 2 | TASK-516 | `origin/qwen-worker-7-r9-task516` | origin | AWAITING_REVIEW | +156/-0 | 2 | 1 | result exists on a live branch, 156-line diff over 2 files, no work/ or config/, no net deletion, stage AWAITING_REVIEW |
| 3 | TASK-250 | `qwen-worker-9-r61` | local+origin | DONE | +161/-8 | 5 | 1 | result exists on a live branch, 169-line diff over 5 files, no work/ or config/, no net deletion, stage DONE |
| 4 | TASK-458 | `origin/qwen-worker-r9-task458` | origin | AWAITING_REVIEW | +182/-1 | 2 | 1 | result exists on a live branch, 183-line diff over 2 files, no work/ or config/, no net deletion, stage AWAITING_REVIEW |
| 5 | TASK-289 | `qwen-worker-6-r60` | local+origin | DONE | +244/-2 | 3 | 1 | result exists on a live branch, 246-line diff over 3 files, no work/ or config/, no net deletion, stage DONE |
| 6 | TASK-488 | `qwen-worker-7-r9-task488` | local+origin | AWAITING_REVIEW | +337/-0 | 2 | 1 | result exists on a live branch, 337-line diff over 2 files, no work/ or config/, no net deletion, stage AWAITING_REVIEW |
| 7 | TASK-262 | `qwen-worker-10-r59` | local+origin | DONE | +219/-124 | 5 | 1 | result exists on a live branch, 343-line diff over 5 files, no work/ or config/, no net deletion, stage DONE |
| 8 | TASK-325 | `qwen-worker-r60` | local+origin | DONE | +364/-0 | 2 | 1 | result exists on a live branch, 364-line diff over 2 files, no work/ or config/, no net deletion, stage DONE |
| 9 | TASK-219 | `qwen-worker-r51` | local+origin | AWAITING_REVIEW | +192/-188 | 7 | 1 | result exists on a live branch, 380-line diff over 7 files, no work/ or config/, no net deletion, stage AWAITING_REVIEW |
| 10 | TASK-269 | `qwen-worker-4-r58` | local+origin | DONE | +386/-9 | 7 | 1 | result exists on a live branch, 395-line diff over 7 files, no work/ or config/, no net deletion, stage DONE |
| 11 | TASK-307 | `qwen-worker-9-r59` | local+origin | DONE | +371/-48 | 6 | 1 | result exists on a live branch, 419-line diff over 6 files, no work/ or config/, no net deletion, stage DONE |
| 12 | TASK-353 | `qwen-worker-9-r68` | local+origin | AWAITING_REVIEW | +424/-0 | 7 | 1 | result exists on a live branch, 424-line diff over 7 files, no work/ or config/, no net deletion, stage AWAITING_REVIEW |
| 13 | TASK-240 | `qwen-worker-r55` | local+origin | DONE | +380/-68 | 4 | 1 | result exists on a live branch, 448-line diff over 4 files, no work/ or config/, no net deletion, stage DONE |
| 14 | TASK-287 | `qwen-worker-4-r60` | local+origin | AWAITING_REVIEW | +449/-3 | 4 | 1 | result exists on a live branch, 452-line diff over 4 files, no work/ or config/, no net deletion, stage AWAITING_REVIEW |
| 15 | TASK-538 | `task-538-triage-batch-01` | local+origin | AWAITING_REVIEW | +490/-0 | 2 | 1 | result exists on a live branch, 490-line diff over 2 files, no work/ or config/, no net deletion, stage AWAITING_REVIEW |
| 16 | TASK-243 | `qwen-worker-2-task-243` | local+origin | DONE | +489/-6 | 14 | 1 | result exists on a live branch, 495-line diff over 14 files, no work/ or config/, no net deletion, stage DONE |
| 17 | TASK-565 | `qwen-worker-8-r31` | local+origin | AWAITING_REVIEW | +519/-0 | 2 | 1 | result exists on a live branch, 519-line diff over 2 files, no work/ or config/, no net deletion, stage AWAITING_REVIEW |
| 18 | TASK-213 | `qwen-worker-4-r45` | local+origin | DONE | +538/-0 | 3 | 1 | result exists on a live branch, 538-line diff over 3 files, no work/ or config/, no net deletion, stage DONE |
| 19 | TASK-266 | `qwen-worker-r58` | local+origin | DONE | +573/-0 | 3 | 1 | result exists on a live branch, 573-line diff over 3 files, no work/ or config/, no net deletion, stage DONE |
| 20 | TASK-221 | `qwen-worker-2-r50` | local+origin | DONE | +540/-40 | 3 | 1 | result exists on a live branch, 580-line diff over 3 files, no work/ or config/, no net deletion, stage DONE |
| 21 | TASK-911 | `qwen-worker-8-r17` | local+origin | AWAITING_REVIEW | +550/-33 | 4 | 1 | result exists on a live branch, 583-line diff over 4 files, no work/ or config/, no net deletion, stage AWAITING_REVIEW |
| 22 | TASK-274 | `qwen-worker-5-r58` | local+origin | DONE | +585/-0 | 7 | 1 | result exists on a live branch, 585-line diff over 7 files, no work/ or config/, no net deletion, stage DONE |
| 23 | TASK-349 | `qwen-worker-6-r68` | local+origin | AWAITING_REVIEW | +515/-73 | 5 | 1 | result exists on a live branch, 588-line diff over 5 files, no work/ or config/, no net deletion, stage AWAITING_REVIEW |
| 24 | TASK-339 | `qwen-worker-2-r63` | local+origin | AWAITING_REVIEW | +550/-91 | 4 | 1 | result exists on a live branch, 641-line diff over 4 files, no work/ or config/, no net deletion, stage AWAITING_REVIEW |
| 25 | TASK-216 | `qwen-worker-3-r47` | local+origin | DONE | +402/-284 | 3 | 1 | result exists on a live branch, 686-line diff over 3 files, no work/ or config/, no net deletion, stage DONE |
| 26 | TASK-288 | `qwen-worker-6-r59` | local+origin | DONE | +692/-8 | 3 | 1 | result exists on a live branch, 700-line diff over 3 files, no work/ or config/, no net deletion, stage DONE |
| 27 | TASK-357 | `qwen-worker-r69` | local+origin | AWAITING_REVIEW | +663/-89 | 4 | 1 | result exists on a live branch, 752-line diff over 4 files, no work/ or config/, no net deletion, stage AWAITING_REVIEW |
| 28 | TASK-271 | `qwen-worker-6-r58` | local+origin | DONE | +811/-0 | 4 | 1 | result exists on a live branch, 811-line diff over 4 files, no work/ or config/, no net deletion, stage DONE |
| 29 | TASK-327 | `qwen-worker-2-r60` | local+origin | DONE | +782/-74 | 4 | 1 | result exists on a live branch, 856-line diff over 4 files, no work/ or config/, no net deletion, stage DONE |
| 30 | TASK-342 | `qwen-worker-r72` | local+origin | AWAITING_REVIEW | +864/-0 | 2 | 1 | result exists on a live branch, 864-line diff over 2 files, no work/ or config/, no net deletion, stage AWAITING_REVIEW |
| 31 | TASK-344 | `qwen-worker-3-r68` | local+origin | AWAITING_REVIEW | +887/-0 | 3 | 1 | result exists on a live branch, 887-line diff over 3 files, no work/ or config/, no net deletion, stage AWAITING_REVIEW |
| 32 | TASK-225 | `qwen-worker-7-r28` | local+origin | DONE | +914/-0 | 3 | 1 | result exists on a live branch, 914-line diff over 3 files, no work/ or config/, no net deletion, stage DONE |
| 33 | TASK-345 | `qwen-worker-r68` | local+origin | AWAITING_REVIEW | +927/-0 | 4 | 1 | result exists on a live branch, 927-line diff over 4 files, no work/ or config/, no net deletion, stage AWAITING_REVIEW |
| 34 | TASK-249 | `qwen-worker-8-r61` | local+origin | DONE | +948/-0 | 5 | 1 | result exists on a live branch, 948-line diff over 5 files, no work/ or config/, no net deletion, stage DONE |
| 35 | TASK-350 | `qwen-worker-7-r68` | local+origin | AWAITING_REVIEW | +1005/-0 | 4 | 1 | result exists on a live branch, 1005-line diff over 4 files, no work/ or config/, no net deletion, stage AWAITING_REVIEW |
| 36 | TASK-192 | `qwen-worker-5-r59` | local+origin | DONE | +983/-105 | 6 | 1 | result exists on a live branch, 1088-line diff over 6 files, no work/ or config/, no net deletion, stage DONE |
| 37 | TASK-935 | `qwen-worker-2-r9` | local+origin | DONE | +1109/-0 | 3 | 1 | result exists on a live branch, 1109-line diff over 3 files, no work/ or config/, no net deletion, stage DONE |
| 38 | TASK-279 | `qwen-worker-4-r9` | local+origin | AWAITING_REVIEW | +1155/-0 | 4 | 1 | result exists on a live branch, 1155-line diff over 4 files, no work/ or config/, no net deletion, stage AWAITING_REVIEW |
| 39 | TASK-301 | `qwen-worker-7-r59` | local+origin | AWAITING_REVIEW | +1173/-0 | 5 | 1 | result exists on a live branch, 1173-line diff over 5 files, no work/ or config/, no net deletion, stage AWAITING_REVIEW |
| 40 | TASK-359 | `qwen-worker-r70` | local+origin | AWAITING_REVIEW | +1175/-0 | 5 | 1 | result exists on a live branch, 1175-line diff over 5 files, no work/ or config/, no net deletion, stage AWAITING_REVIEW |
| 41 | TASK-248 | `qwen-worker-7-task-248` | local+origin | DONE | +1177/-0 | 8 | 1 | result exists on a live branch, 1177-line diff over 8 files, no work/ or config/, no net deletion, stage DONE |
| 42 | TASK-230 | `task-230-prefetch-headcount` | local+origin | DONE | +1076/-124 | 6 | 1 | result exists on a live branch, 1200-line diff over 6 files, no work/ or config/, no net deletion, stage DONE |
| 43 | TASK-340 | `qwen-worker-4-r67` | local+origin | AWAITING_REVIEW | +1210/-86 | 7 | 1 | result exists on a live branch, 1296-line diff over 7 files, no work/ or config/, no net deletion, stage AWAITING_REVIEW |
| 44 | TASK-286 | `qwen-worker-3-r60` | local+origin | DONE | +1230/-130 | 4 | 1 | result exists on a live branch, 1360-line diff over 4 files, no work/ or config/, no net deletion, stage DONE |
| 45 | TASK-295 | `qwen-worker-4-r9-task295` | local+origin | DONE | +1417/-5 | 6 | 1 | result exists on a live branch, 1422-line diff over 6 files, no work/ or config/, no net deletion, stage DONE |
| 46 | TASK-312 | `qwen-worker-4-r59` | local+origin | DONE | +1439/-0 | 3 | 1 | result exists on a live branch, 1439-line diff over 3 files, no work/ or config/, no net deletion, stage DONE |
| 47 | TASK-304 | `origin/qwen-worker-4-task304-review-file` | origin | AWAITING_REVIEW | +1610/-23 | 6 | 1 | result exists on a live branch, 1633-line diff over 6 files, no work/ or config/, no net deletion, stage AWAITING_REVIEW |
| 48 | TASK-284 | `qwen-worker-12-r59` | local+origin | DONE | +1788/-3 | 9 | 1 | result exists on a live branch, 1791-line diff over 9 files, no work/ or config/, no net deletion, stage DONE |
| 49 | TASK-231 | `origin/qwen-worker-7-r9` | origin | AWAITING_REVIEW | +2048/-118 | 14 | 6 | result exists on a live branch, 2166-line diff over 14 files, no work/ or config/, no net deletion, stage AWAITING_REVIEW |
| 50 | TASK-273 | `origin/qwen-worker-7-r9` | origin | DONE | +2048/-118 | 14 | 6 | result exists on a live branch, 2166-line diff over 14 files, no work/ or config/, no net deletion, stage DONE |
| 51 | TASK-484 | `origin/qwen-worker-7-r9` | origin | AWAITING_REVIEW | +2048/-118 | 14 | 6 | result exists on a live branch, 2166-line diff over 14 files, no work/ or config/, no net deletion, stage AWAITING_REVIEW |
| 52 | TASK-512 | `origin/qwen-worker-7-r9` | origin | AWAITING_REVIEW | +2048/-118 | 14 | 6 | result exists on a live branch, 2166-line diff over 14 files, no work/ or config/, no net deletion, stage AWAITING_REVIEW |
| 53 | TASK-532 | `origin/qwen-worker-7-r9` | origin | DONE | +2048/-118 | 14 | 6 | result exists on a live branch, 2166-line diff over 14 files, no work/ or config/, no net deletion, stage DONE |
| 54 | TASK-933 | `origin/qwen-worker-7-r9` | origin | AWAITING_REVIEW | +2048/-118 | 14 | 6 | result exists on a live branch, 2166-line diff over 14 files, no work/ or config/, no net deletion, stage AWAITING_REVIEW |
| 55 | TASK-352 | `origin/qwen-worker-4-r9` | origin | AWAITING_REVIEW | +2560/-80 | 24 | 2 | result exists on a live branch, 2640-line diff over 24 files, no work/ or config/, no net deletion, stage AWAITING_REVIEW |
| 56 | TASK-438 | `origin/qwen-worker-4-r9` | origin | DONE | +2560/-80 | 24 | 2 | result exists on a live branch, 2640-line diff over 24 files, no work/ or config/, no net deletion, stage DONE |
| 57 | TASK-281 | `qwen-worker-r9` | local+origin | AWAITING_REVIEW | +3238/-0 | 39 | 1 | result exists on a live branch, 3238-line diff over 39 files, no work/ or config/, no net deletion, stage AWAITING_REVIEW |
| 58 | TASK-280 | `qwen-worker-4-r9-task280` | local+origin | AWAITING_REVIEW | +3700/-9 | 13 | 3 | result exists on a live branch, 3709-line diff over 13 files, no work/ or config/, no net deletion, stage AWAITING_REVIEW |
| 59 | TASK-308 | `qwen-worker-4-r9-task280` | local+origin | AWAITING_REVIEW | +3700/-9 | 13 | 3 | result exists on a live branch, 3709-line diff over 13 files, no work/ or config/, no net deletion, stage AWAITING_REVIEW |
| 60 | TASK-315 | `qwen-worker-4-r9-task280` | local+origin | AWAITING_REVIEW | +3700/-9 | 13 | 3 | result exists on a live branch, 3709-line diff over 13 files, no work/ or config/, no net deletion, stage AWAITING_REVIEW |
| 61 | TASK-296 | `qwen-worker-11-task314` | local+origin | AWAITING_REVIEW | +4441/-200 | 23 | 4 | result exists on a live branch, 4641-line diff over 23 files, no work/ or config/, no net deletion, stage AWAITING_REVIEW |
| 62 | TASK-314 | `qwen-worker-11-task314` | local+origin | DONE | +4441/-200 | 23 | 4 | result exists on a live branch, 4641-line diff over 23 files, no work/ or config/, no net deletion, stage DONE |
| 63 | TASK-398 | `qwen-worker-11-task314` | local+origin | AWAITING_REVIEW | +4441/-200 | 23 | 4 | result exists on a live branch, 4641-line diff over 23 files, no work/ or config/, no net deletion, stage AWAITING_REVIEW |
| 64 | TASK-413 | `qwen-worker-11-task314` | local+origin | AWAITING_REVIEW | +4441/-200 | 23 | 4 | result exists on a live branch, 4641-line diff over 23 files, no work/ or config/, no net deletion, stage AWAITING_REVIEW |
| 65 | TASK-328 | `qwen-worker-12-r9` | local+origin | AWAITING_REVIEW | +4570/-76 | 45 | 7 | result exists on a live branch, 4646-line diff over 45 files, no work/ or config/, no net deletion, stage AWAITING_REVIEW |
| 66 | TASK-395 | `qwen-worker-12-r9` | local+origin | DONE | +4570/-76 | 45 | 7 | result exists on a live branch, 4646-line diff over 45 files, no work/ or config/, no net deletion, stage DONE |
| 67 | TASK-441 | `qwen-worker-12-r9` | local+origin | DONE | +4570/-76 | 45 | 7 | result exists on a live branch, 4646-line diff over 45 files, no work/ or config/, no net deletion, stage DONE |
| 68 | TASK-449 | `qwen-worker-12-r9` | local+origin | DONE | +4570/-76 | 45 | 7 | result exists on a live branch, 4646-line diff over 45 files, no work/ or config/, no net deletion, stage DONE |
| 69 | TASK-459 | `qwen-worker-12-r9` | local+origin | AWAITING_REVIEW | +4570/-76 | 45 | 7 | result exists on a live branch, 4646-line diff over 45 files, no work/ or config/, no net deletion, stage AWAITING_REVIEW |
| 70 | TASK-467 | `qwen-worker-12-r9` | local+origin | DONE | +4570/-76 | 45 | 7 | result exists on a live branch, 4646-line diff over 45 files, no work/ or config/, no net deletion, stage DONE |
| 71 | TASK-473 | `qwen-worker-12-r9` | local+origin | DONE | +4570/-76 | 45 | 7 | result exists on a live branch, 4646-line diff over 45 files, no work/ or config/, no net deletion, stage DONE |
| 72 | TASK-294 | `qwen-worker-r9-t391` | local+origin | AWAITING_REVIEW | +5285/-212 | 46 | 4 | result exists on a live branch, 5497-line diff over 46 files, no work/ or config/, no net deletion, stage AWAITING_REVIEW |
| 73 | TASK-311 | `qwen-worker-r9-t391` | local+origin | AWAITING_REVIEW | +5285/-212 | 46 | 4 | result exists on a live branch, 5497-line diff over 46 files, no work/ or config/, no net deletion, stage AWAITING_REVIEW |
| 74 | TASK-418 | `qwen-worker-r9-t391` | local+origin | DONE | +5285/-212 | 46 | 4 | result exists on a live branch, 5497-line diff over 46 files, no work/ or config/, no net deletion, stage DONE |
| 75 | TASK-463 | `qwen-worker-r9-t391` | local+origin | AWAITING_REVIEW | +5285/-212 | 46 | 4 | result exists on a live branch, 5497-line diff over 46 files, no work/ or config/, no net deletion, stage AWAITING_REVIEW |
| 76 | TASK-318 | `qwen-worker-10-r9` | local+origin | AWAITING_REVIEW | +5597/-78 | 32 | 13 | result exists on a live branch, 5675-line diff over 32 files, no work/ or config/, no net deletion, stage AWAITING_REVIEW |
| 77 | TASK-397 | `qwen-worker-10-r9` | local+origin | AWAITING_REVIEW | +5597/-78 | 32 | 13 | result exists on a live branch, 5675-line diff over 32 files, no work/ or config/, no net deletion, stage AWAITING_REVIEW |
| 78 | TASK-411 | `qwen-worker-10-r9` | local+origin | DONE | +5597/-78 | 32 | 13 | result exists on a live branch, 5675-line diff over 32 files, no work/ or config/, no net deletion, stage DONE |
| 79 | TASK-491 | `qwen-worker-10-r9` | local+origin | AWAITING_REVIEW | +5597/-78 | 32 | 13 | result exists on a live branch, 5675-line diff over 32 files, no work/ or config/, no net deletion, stage AWAITING_REVIEW |
| 80 | TASK-504 | `qwen-worker-10-r9` | local+origin | DONE | +5597/-78 | 32 | 13 | result exists on a live branch, 5675-line diff over 32 files, no work/ or config/, no net deletion, stage DONE |
| 81 | TASK-514 | `qwen-worker-10-r9` | local+origin | DONE | +5597/-78 | 32 | 13 | result exists on a live branch, 5675-line diff over 32 files, no work/ or config/, no net deletion, stage DONE |
| 82 | TASK-520 | `qwen-worker-10-r9` | local+origin | DONE | +5597/-78 | 32 | 13 | result exists on a live branch, 5675-line diff over 32 files, no work/ or config/, no net deletion, stage DONE |
| 83 | TASK-522 | `qwen-worker-10-r9` | local+origin | DONE | +5597/-78 | 32 | 13 | result exists on a live branch, 5675-line diff over 32 files, no work/ or config/, no net deletion, stage DONE |
| 84 | TASK-527 | `qwen-worker-10-r9` | local+origin | DONE | +5597/-78 | 32 | 13 | result exists on a live branch, 5675-line diff over 32 files, no work/ or config/, no net deletion, stage DONE |
| 85 | TASK-534 | `qwen-worker-10-r9` | local+origin | DONE | +5597/-78 | 32 | 13 | result exists on a live branch, 5675-line diff over 32 files, no work/ or config/, no net deletion, stage DONE |
| 86 | TASK-539 | `qwen-worker-10-r9` | local+origin | DONE | +5597/-78 | 32 | 13 | result exists on a live branch, 5675-line diff over 32 files, no work/ or config/, no net deletion, stage DONE |
| 87 | TASK-932 | `qwen-worker-10-r9` | local+origin | DONE | +5597/-78 | 32 | 13 | result exists on a live branch, 5675-line diff over 32 files, no work/ or config/, no net deletion, stage DONE |
| 88 | TASK-973 | `qwen-worker-10-r9` | local+origin | AWAITING_REVIEW | +5597/-78 | 32 | 13 | result exists on a live branch, 5675-line diff over 32 files, no work/ or config/, no net deletion, stage AWAITING_REVIEW |
| 89 | TASK-246 | `origin/qwen-worker-6-r9` | origin | AWAITING_REVIEW | +5887/-413 | 43 | 8 | result exists on a live branch, 6300-line diff over 43 files, no work/ or config/, no net deletion, stage AWAITING_REVIEW |
| 90 | TASK-391 | `origin/qwen-worker-6-r9` | origin | DONE | +5887/-413 | 43 | 8 | result exists on a live branch, 6300-line diff over 43 files, no work/ or config/, no net deletion, stage DONE |
| 91 | TASK-419 | `origin/qwen-worker-6-r9` | origin | DONE | +5887/-413 | 43 | 8 | result exists on a live branch, 6300-line diff over 43 files, no work/ or config/, no net deletion, stage DONE |
| 92 | TASK-423 | `origin/qwen-worker-6-r9` | origin | AWAITING_REVIEW | +5887/-413 | 43 | 8 | result exists on a live branch, 6300-line diff over 43 files, no work/ or config/, no net deletion, stage AWAITING_REVIEW |
| 93 | TASK-439 | `origin/qwen-worker-6-r9` | origin | AWAITING_REVIEW | +5887/-413 | 43 | 8 | result exists on a live branch, 6300-line diff over 43 files, no work/ or config/, no net deletion, stage AWAITING_REVIEW |
| 94 | TASK-445 | `origin/qwen-worker-6-r9` | origin | AWAITING_REVIEW | +5887/-413 | 43 | 8 | result exists on a live branch, 6300-line diff over 43 files, no work/ or config/, no net deletion, stage AWAITING_REVIEW |
| 95 | TASK-455 | `origin/qwen-worker-6-r9` | origin | AWAITING_REVIEW | +5887/-413 | 43 | 8 | result exists on a live branch, 6300-line diff over 43 files, no work/ or config/, no net deletion, stage AWAITING_REVIEW |
| 96 | TASK-461 | `origin/qwen-worker-6-r9` | origin | AWAITING_REVIEW | +5887/-413 | 43 | 8 | result exists on a live branch, 6300-line diff over 43 files, no work/ or config/, no net deletion, stage AWAITING_REVIEW |
| 97 | TASK-226 | `origin/qwen-worker-5-r9` | origin | AWAITING_REVIEW | +6486/-249 | 44 | 15 | result exists on a live branch, 6735-line diff over 44 files, no work/ or config/, no net deletion, stage AWAITING_REVIEW |
| 98 | TASK-403 | `origin/qwen-worker-5-r9` | origin | AWAITING_REVIEW | +6486/-249 | 44 | 15 | result exists on a live branch, 6735-line diff over 44 files, no work/ or config/, no net deletion, stage AWAITING_REVIEW |
| 99 | TASK-470 | `origin/qwen-worker-5-r9` | origin | AWAITING_REVIEW | +6486/-249 | 44 | 15 | result exists on a live branch, 6735-line diff over 44 files, no work/ or config/, no net deletion, stage AWAITING_REVIEW |
| 100 | TASK-489 | `origin/qwen-worker-5-r9` | origin | DONE | +6486/-249 | 44 | 15 | result exists on a live branch, 6735-line diff over 44 files, no work/ or config/, no net deletion, stage DONE |
| 101 | TASK-497 | `origin/qwen-worker-5-r9` | origin | DONE | +6486/-249 | 44 | 15 | result exists on a live branch, 6735-line diff over 44 files, no work/ or config/, no net deletion, stage DONE |
| 102 | TASK-499 | `origin/qwen-worker-5-r9` | origin | AWAITING_REVIEW | +6486/-249 | 44 | 15 | result exists on a live branch, 6735-line diff over 44 files, no work/ or config/, no net deletion, stage AWAITING_REVIEW |
| 103 | TASK-501 | `origin/qwen-worker-5-r9` | origin | AWAITING_REVIEW | +6486/-249 | 44 | 15 | result exists on a live branch, 6735-line diff over 44 files, no work/ or config/, no net deletion, stage AWAITING_REVIEW |
| 104 | TASK-508 | `origin/qwen-worker-5-r9` | origin | DONE | +6486/-249 | 44 | 15 | result exists on a live branch, 6735-line diff over 44 files, no work/ or config/, no net deletion, stage DONE |
| 105 | TASK-524 | `origin/qwen-worker-5-r9` | origin | DONE | +6486/-249 | 44 | 15 | result exists on a live branch, 6735-line diff over 44 files, no work/ or config/, no net deletion, stage DONE |
| 106 | TASK-531 | `origin/qwen-worker-5-r9` | origin | DONE | +6486/-249 | 44 | 15 | result exists on a live branch, 6735-line diff over 44 files, no work/ or config/, no net deletion, stage DONE |
| 107 | TASK-537 | `origin/qwen-worker-5-r9` | origin | DONE | +6486/-249 | 44 | 15 | result exists on a live branch, 6735-line diff over 44 files, no work/ or config/, no net deletion, stage DONE |
| 108 | TASK-541 | `origin/qwen-worker-5-r9` | origin | AWAITING_REVIEW | +6486/-249 | 44 | 15 | result exists on a live branch, 6735-line diff over 44 files, no work/ or config/, no net deletion, stage AWAITING_REVIEW |
| 109 | TASK-548 | `origin/qwen-worker-5-r9` | origin | AWAITING_REVIEW | +6486/-249 | 44 | 15 | result exists on a live branch, 6735-line diff over 44 files, no work/ or config/, no net deletion, stage AWAITING_REVIEW |
| 110 | TASK-903 | `origin/qwen-worker-5-r9` | origin | DONE | +6486/-249 | 44 | 15 | result exists on a live branch, 6735-line diff over 44 files, no work/ or config/, no net deletion, stage DONE |
| 111 | TASK-931 | `origin/qwen-worker-5-r9` | origin | AWAITING_REVIEW | +6486/-249 | 44 | 15 | result exists on a live branch, 6735-line diff over 44 files, no work/ or config/, no net deletion, stage AWAITING_REVIEW |
| 112 | TASK-267 | `qwen-worker-3-r9-task285` | local+origin | AWAITING_REVIEW | +7167/-223 | 39 | 6 | result exists on a live branch, 7390-line diff over 39 files, no work/ or config/, no net deletion, stage AWAITING_REVIEW |
| 113 | TASK-285 | `qwen-worker-3-r9-task285` | local+origin | AWAITING_REVIEW | +7167/-223 | 39 | 6 | result exists on a live branch, 7390-line diff over 39 files, no work/ or config/, no net deletion, stage AWAITING_REVIEW |
| 114 | TASK-358 | `qwen-worker-3-r9-task285` | local+origin | AWAITING_REVIEW | +7167/-223 | 39 | 6 | result exists on a live branch, 7390-line diff over 39 files, no work/ or config/, no net deletion, stage AWAITING_REVIEW |
| 115 | TASK-410 | `qwen-worker-3-r9-task285` | local+origin | AWAITING_REVIEW | +7167/-223 | 39 | 6 | result exists on a live branch, 7390-line diff over 39 files, no work/ or config/, no net deletion, stage AWAITING_REVIEW |
| 116 | TASK-412 | `qwen-worker-3-r9-task285` | local+origin | AWAITING_REVIEW | +7167/-223 | 39 | 6 | result exists on a live branch, 7390-line diff over 39 files, no work/ or config/, no net deletion, stage AWAITING_REVIEW |
| 117 | TASK-432 | `qwen-worker-3-r9-task285` | local+origin | AWAITING_REVIEW | +7167/-223 | 39 | 6 | result exists on a live branch, 7390-line diff over 39 files, no work/ or config/, no net deletion, stage AWAITING_REVIEW |
| 118 | TASK-901 | `task-901-figure-gate-fix` | local+origin | AWAITING_REVIEW | +16166/-83 | 31 | 1 | result exists on a live branch, 16249-line diff over 31 files, no work/ or config/, no net deletion, stage AWAITING_REVIEW |
| 119 | TASK-264 | `qwen-worker-7-r9-task518` | local+origin | AWAITING_REVIEW | +16314/-602 | 116 | 29 | result exists on a live branch, 16916-line diff over 116 files, no work/ or config/, no net deletion, stage AWAITING_REVIEW |
| 120 | TASK-326 | `qwen-worker-7-r9-task518` | local+origin | AWAITING_REVIEW | +16314/-602 | 116 | 29 | result exists on a live branch, 16916-line diff over 116 files, no work/ or config/, no net deletion, stage AWAITING_REVIEW |
| 121 | TASK-389 | `qwen-worker-7-r9-task518` | local+origin | AWAITING_REVIEW | +16314/-602 | 116 | 29 | result exists on a live branch, 16916-line diff over 116 files, no work/ or config/, no net deletion, stage AWAITING_REVIEW |
| 122 | TASK-406 | `qwen-worker-7-r9-task518` | local+origin | AWAITING_REVIEW | +16314/-602 | 116 | 29 | result exists on a live branch, 16916-line diff over 116 files, no work/ or config/, no net deletion, stage AWAITING_REVIEW |
| 123 | TASK-429 | `qwen-worker-7-r9-task518` | local+origin | AWAITING_REVIEW | +16314/-602 | 116 | 29 | result exists on a live branch, 16916-line diff over 116 files, no work/ or config/, no net deletion, stage AWAITING_REVIEW |
| 124 | TASK-431 | `qwen-worker-7-r9-task518` | local+origin | AWAITING_REVIEW | +16314/-602 | 116 | 29 | result exists on a live branch, 16916-line diff over 116 files, no work/ or config/, no net deletion, stage AWAITING_REVIEW |
| 125 | TASK-440 | `qwen-worker-7-r9-task518` | local+origin | DONE | +16314/-602 | 116 | 29 | result exists on a live branch, 16916-line diff over 116 files, no work/ or config/, no net deletion, stage DONE |
| 126 | TASK-443 | `qwen-worker-7-r9-task518` | local+origin | AWAITING_REVIEW | +16314/-602 | 116 | 29 | result exists on a live branch, 16916-line diff over 116 files, no work/ or config/, no net deletion, stage AWAITING_REVIEW |
| 127 | TASK-446 | `qwen-worker-7-r9-task518` | local+origin | DONE | +16314/-602 | 116 | 29 | result exists on a live branch, 16916-line diff over 116 files, no work/ or config/, no net deletion, stage DONE |
| 128 | TASK-450 | `qwen-worker-7-r9-task518` | local+origin | DONE | +16314/-602 | 116 | 29 | result exists on a live branch, 16916-line diff over 116 files, no work/ or config/, no net deletion, stage DONE |
| 129 | TASK-453 | `qwen-worker-7-r9-task518` | local+origin | AWAITING_REVIEW | +16314/-602 | 116 | 29 | result exists on a live branch, 16916-line diff over 116 files, no work/ or config/, no net deletion, stage AWAITING_REVIEW |
| 130 | TASK-457 | `qwen-worker-7-r9-task518` | local+origin | AWAITING_REVIEW | +16314/-602 | 116 | 29 | result exists on a live branch, 16916-line diff over 116 files, no work/ or config/, no net deletion, stage AWAITING_REVIEW |
| 131 | TASK-464 | `qwen-worker-7-r9-task518` | local+origin | DONE | +16314/-602 | 116 | 29 | result exists on a live branch, 16916-line diff over 116 files, no work/ or config/, no net deletion, stage DONE |
| 132 | TASK-466 | `qwen-worker-7-r9-task518` | local+origin | AWAITING_REVIEW | +16314/-602 | 116 | 29 | result exists on a live branch, 16916-line diff over 116 files, no work/ or config/, no net deletion, stage AWAITING_REVIEW |
| 133 | TASK-469 | `qwen-worker-7-r9-task518` | local+origin | AWAITING_REVIEW | +16314/-602 | 116 | 29 | result exists on a live branch, 16916-line diff over 116 files, no work/ or config/, no net deletion, stage AWAITING_REVIEW |
| 134 | TASK-471 | `qwen-worker-7-r9-task518` | local+origin | DONE | +16314/-602 | 116 | 29 | result exists on a live branch, 16916-line diff over 116 files, no work/ or config/, no net deletion, stage DONE |
| 135 | TASK-476 | `qwen-worker-7-r9-task518` | local+origin | DONE | +16314/-602 | 116 | 29 | result exists on a live branch, 16916-line diff over 116 files, no work/ or config/, no net deletion, stage DONE |
| 136 | TASK-477 | `qwen-worker-7-r9-task518` | local+origin | DONE | +16314/-602 | 116 | 29 | result exists on a live branch, 16916-line diff over 116 files, no work/ or config/, no net deletion, stage DONE |
| 137 | TASK-479 | `qwen-worker-7-r9-task518` | local+origin | DONE | +16314/-602 | 116 | 29 | result exists on a live branch, 16916-line diff over 116 files, no work/ or config/, no net deletion, stage DONE |
| 138 | TASK-480 | `qwen-worker-7-r9-task518` | local+origin | DONE | +16314/-602 | 116 | 29 | result exists on a live branch, 16916-line diff over 116 files, no work/ or config/, no net deletion, stage DONE |
| 139 | TASK-483 | `qwen-worker-7-r9-task518` | local+origin | AWAITING_REVIEW | +16314/-602 | 116 | 29 | result exists on a live branch, 16916-line diff over 116 files, no work/ or config/, no net deletion, stage AWAITING_REVIEW |
| 140 | TASK-485 | `qwen-worker-7-r9-task518` | local+origin | AWAITING_REVIEW | +16314/-602 | 116 | 29 | result exists on a live branch, 16916-line diff over 116 files, no work/ or config/, no net deletion, stage AWAITING_REVIEW |
| 141 | TASK-492 | `qwen-worker-7-r9-task518` | local+origin | DONE | +16314/-602 | 116 | 29 | result exists on a live branch, 16916-line diff over 116 files, no work/ or config/, no net deletion, stage DONE |
| 142 | TASK-495 | `qwen-worker-7-r9-task518` | local+origin | DONE | +16314/-602 | 116 | 29 | result exists on a live branch, 16916-line diff over 116 files, no work/ or config/, no net deletion, stage DONE |
| 143 | TASK-496 | `qwen-worker-7-r9-task518` | local+origin | AWAITING_REVIEW | +16314/-602 | 116 | 29 | result exists on a live branch, 16916-line diff over 116 files, no work/ or config/, no net deletion, stage AWAITING_REVIEW |
| 144 | TASK-502 | `qwen-worker-7-r9-task518` | local+origin | DONE | +16314/-602 | 116 | 29 | result exists on a live branch, 16916-line diff over 116 files, no work/ or config/, no net deletion, stage DONE |
| 145 | TASK-507 | `qwen-worker-7-r9-task518` | local+origin | AWAITING_REVIEW | +16314/-602 | 116 | 29 | result exists on a live branch, 16916-line diff over 116 files, no work/ or config/, no net deletion, stage AWAITING_REVIEW |
| 146 | TASK-511 | `qwen-worker-7-r9-task518` | local+origin | AWAITING_REVIEW | +16314/-602 | 116 | 29 | result exists on a live branch, 16916-line diff over 116 files, no work/ or config/, no net deletion, stage AWAITING_REVIEW |
| 147 | TASK-518 | `qwen-worker-7-r9-task518` | local+origin | AWAITING_REVIEW | +16314/-602 | 116 | 29 | result exists on a live branch, 16916-line diff over 116 files, no work/ or config/, no net deletion, stage AWAITING_REVIEW |

Parked tasks and their reasons: `docs/state/PARKED-2026-10-12.md`.
