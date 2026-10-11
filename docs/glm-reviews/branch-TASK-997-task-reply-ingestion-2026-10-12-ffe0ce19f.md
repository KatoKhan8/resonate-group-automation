# GLM branch verification: TASK-997

Branch: `task-reply-ingestion-2026-10-12`
Date: 2026-10-11T23:47:11.490117+00:00
Model: glm-5.3
Duration: 164.818s
Usage: {'prompt_tokens': 13845, 'completion_tokens': 12712, 'total_tokens': 26557, 'reasoning_tokens': 11673, 'cached_tokens': 13824}

## Verdict: FAIL

**`_append` in the walk script appends with no `stored_reply_ids` dedup, so losing the walk's state file re-stores the entire history — the "same reply stored once" criterion is defeated by one of the branch's own two writers, at ~180k-row scale.**

## GLM spend

This call: 1 ledger rows, 25877 micro-USD

## Changed files (8)

- `scripts/learning_walk_replies.py`
- `src/adapters.py`
- `src/inbound.py`
- `src/poller.py`
- `src/replies.py`
- `src/replywatch.py`
- `src/store.py`
- `tests/test_the_reply_store_is_not_inert.py`

## Diff stat

```
 scripts/learning_walk_replies.py           |  80 ++++-
 src/adapters.py                            |  16 +
 src/inbound.py                             |  21 ++
 src/poller.py                              |   8 +
 src/replies.py                             | 209 ++++++++++++
 src/replywatch.py                          |  12 +-
 src/store.py                               |  27 +-
 tests/test_the_reply_store_is_not_inert.py | 489 +++++++++++++++++++++++++++++
 8 files changed, 849 insertions(+), 13 deletions(-)

```

## Acceptance output

```
NOTHING WAS RUN. This task declares no runnable acceptance commands, so there is no evidence here that the branch does what it claims. Treat question 2 as unanswerable and do not return PASS on the strength of the diff alone.

The task's acceptance criteria, stated as prose rather than as commands, are below. Judge the diff AGAINST THESE - that is what the branch promised:

- A positive control proving ingestion can **fail loudly** rather than silently
  returning zero: make the store write fail and require the watcher to surface
  unhealthy, NOT `new_replies_ingested: 0` beside `healthy: true`.
- A test proving a real reply IS ingested and counted. A zero never shown able
  to be non-zero is not a result.
- An **unattributed** reply must be stored and counted, not dropped. That is the
  whole defect.
- Our own outgoing mail must never enter the reply store.
- The same reply read twice is stored once.
- Backward compatibility: legacy rows carry no verdict and must not crash a
  reader, and must NOT read as classified. Absent verdict is UNKNOWN, never a
  pass. `src/replyverdict.py` already compares `RULE_HASH`; match what it
  expects rather than inventing a field.
- No reply body, name or address persisted beyond what the schema states.

(no acceptance commands extracted from task file)
```

## GLM response

## 1. Production caller?

YES. `src/inbound.py` (`ingest`, new code just before the `handle` loop): `stored = replies.remember(neutral, model=model)` → `poller.run` consumes `outcome["stored"]` → `replywatch.poll_once` reports `replies_stored`. `replies.store_row`/`verdict_fields`/`stored_reply_ids` are called from `remember`; `store.reply_store_path` is called from both `replies.py` and `scripts/learning_walk_replies.py`. The bridge has callers on both sides.

## 2. Can the acceptance check fail?

The 12 tests are non-vacuous: if `remember` swallowed the write error, `test_a_failed_store_write_makes_the_watcher_unhealthy` fails (input: `LEARNING_REPLIES` whose parent is a file); if the id-keyed dedup were removed, `test_the_same_reply_read_twice_is_stored_once` fails; if outgoing mail passed `is_reply`, the outgoing test fails. But two gaps: **no acceptance commands exist**, and **only the new test file was run** — `inbound.ingest`, `poller.run`, `adapters.from_emailbison`, and `store.STATE_OVERRIDES` all changed with zero regression-suite evidence.

## 3. Do the numbers reconcile?

- 12 tests run = 2 + 5 + 5 listed. ✓
- **The store row-counts do NOT reconcile.** The branch asserts three facts: the file had 32,025 lines on 2026-09-22 (`replies.remember` docstring), it "had not been written since 23 September" (test module docstring), and "the 179,715 existing rows" (test docstring, `test_a_row_with_no_verdict...`). 32,025 → 179,715 requires ~147k lines written after 9/22 by a writer that supposedly stopped 9/23 and whose prior ~7-month total was ≤32k (a ~460× one-day rate spike). At most two of the three claims are true; which one is false is not determinable from the diff.

## Findings

1. **FAIL-level: the walk writer has no idempotence, defeating "the same reply read twice is stored once."** `scripts/learning_walk_replies.py` `_append` (new, ~lines 193–206) writes `payload` with no `stored_reply_ids` check — dedup exists only in `replies.remember`. Concrete input: lose/corrupt `work/learning-replies.state.json` (state is `complete:false` since 2026-02-25, so a fresh walk restarts at the head and descends through all history) → the walk re-appends every historical row *and* every watcher-stored head row, including e.g. reply 900999 stored by the watcher the day before. At the branch's own claimed 179,715 rows that is a second copy of essentially the whole file — the exact 2026-09-22 mode (32,025 lines in a 16,650-reply file) the branch cites as the thing it fixed. Read-side counts stay true; the file and the per-poll scan below double.
2. **O(N) full-file parse per poll, under the lock shared with the walk.** `replies.remember` calls `stored_reply_ids(target)` inside `store.lock(for_path=target)` on every cycle with ≥1 reply. Append-only + a 30-month walk means N grows forever; at the claimed N≈179,715 (~27MB) that is a full JSON parse + str-set build every few minutes, and the walk's per-page `_append` blocks behind each one.
3. **Conditional cost: double classification of attributed replies.** A matched reply is classified once in `remember`→`verdict_fields` and again downstream in `handle`. Rules decide clear cases free, so this costs only on the matched-and-unclear subset — 2× model spend there.
4. Not constructible from the diff: `key = str(row.get("reply_id"))` collapses to `"None"` if an event carries neither `reply_id` nor `provider_event_id`, permanently storing only the first such reply. I cannot show a provider emits such events, so: NO FINDING beyond the note.

## Also-check

All eight changed files answer to TASK-997 (store, caller, adapter keys, surfacing, tests). No scratch files at repo root.

VERDICT: FAIL - `_append` in the walk script appends with no `stored_reply_ids` dedup, so losing the walk's state file re-stores the entire history — the "same reply stored once" criterion is defeated by one of the branch's own two writers, at ~180k-row scale.
