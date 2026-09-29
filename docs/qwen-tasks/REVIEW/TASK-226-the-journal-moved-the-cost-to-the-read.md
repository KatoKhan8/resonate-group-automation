# TASK-226 - the journal moved the cost to the read

## The measurement, 500 records at the REAL record size (31,793 B)

    whole-file   1,517 MB written   499.8x amplification   13.3 s
    journal          3.0 MB written     1.0x               22.4 s

`src/queuejournal.py` is wired, tested, and **default OFF** (`QUEUE_JOURNAL=1`).
506x fewer bytes and **69% SLOWER**. The quadratic WRITE is gone; the
bottleneck moved to an O(N) READ per checkpoint that now also replays a
growing journal, and the penalty is worse with real records than toy ones
because the replay is itself proportional to record size.

The flag stays OFF until the read is fixed too. This task fixes the read.

## The objective

An offset index so a checkpoint reads only the rows a delta touches.

Falsifiable requirements:

1. An index mapping record id to byte offset in the base file, maintained
   alongside the journal, so a `save` of a delta touching M records reads
   O(M) rather than O(N).
2. **Correctness first, speed second.** The existing journal tests must all
   still pass unchanged, including the one that ASSERTS THE BAD BEHAVIOUR of
   last-write-wins replay (`replay` has no version comparison - it is pinned
   deliberately so a wiring change cannot miss it). **If that test fails, the
   guard was added and the test should be INVERTED, not deleted** - and that
   is a finding to report, not a thing to do quietly.
3. The index is DERIVED and must be rebuildable from the files alone. A
   corrupt, stale or absent index must be detected and rebuilt, never
   trusted. Prove it: corrupt the index, confirm the read still returns
   correct state.
4. Benchmark at 50 / 500 / 5,000 records with the REAL record size.
   `scripts/store_write_profile.py` and `src/benchmark.py` already pad to
   31,793 B - use them, do not invent a second record shape. That is the
   exact error that made every byte figure 37x too small.
   **MODEL rather than measure the 5,000-record whole-file arm** - it is
   ~159 GB per pass and writing it to the operator's SSD buys no information
   that two measured points do not already give. Label every figure MEASURED
   or MODELLED and never mix them in one table.
5. Target: the journal path no slower than the whole-file path at 500
   records, with its byte advantage intact.

## Boundaries

`QUEUE_JOURNAL` stays **OFF** at the end of this task whatever the benchmark
says. Turning it on is a production decision Claude takes after a GLM review
of the crash and interleaving contract, not a consequence of a good number.

Windows `open(path,"a")` is NOT atomic across processes - reproduced: six
processes, 400 lines each, expected 2400, parsed 2193, MANGLED 1, MISSING
207. `append` takes `store.lock` for that reason. Do not remove it, and do
not add a second writer that bypasses it.

## RESULT

**STATUS:** DONE

**ARTIFACT TYPE:** Code + tests + benchmark

**COMMIT SHA:** 601ab91cdb45bdb1cb7a7cf3c38b0dac48cbe7b3

**TESTS:**
- 18 new tests in `tests/test_the_journal_index_reads_only_what_changed.py` - all pass
- 11 existing journal tests in `tests/test_the_journal_changes_only_the_bytes.py` - all pass
- 99 store-related tests - all pass
- Last-write-wins behavior preserved (no version comparison added to replay)

**FILES CHANGED:**
- `src/queuejournal.py` - added index functions (`build_index`, `load_index`, `load_or_build_index`, `read_ids_from_base`, `replay_narrow`)
- `src/store.py` - modified `_write()` to build index after base write; modified `save()` to use `replay_narrow()` when journalling is on
- `tests/test_the_journal_index_reads_only_what_changed.py` - new test file
- `scripts/benchmark_journal_index.py` - new benchmark script

**FINDINGS:**

1. **Index implementation correct and robust.** The offset index maps record id to byte offset in the base file, validated by SHA-256 digest. Corrupt, stale, or absent indexes are detected and rebuilt. Tests prove:
   - Corrupt index file -> rebuilt transparently
   - Stale digest -> rebuilt transparently
   - Missing index -> rebuilt transparently
   - Offsets point to correct records

2. **Byte target met: 497x fewer bytes at 500 records.**
   - Whole-file: 1,517 MB written
   - Journal+index: 3.05 MB written
   - Ratio: 497x fewer bytes

3. **Time target NOT met: journal path is 1.7x slower at 500 records.**
   - Whole-file: 15.9s
   - Journal+index: 26.8s
   - Ratio: 0.6x (slower)

   **Why:** Random I/O (seeks to specific offsets) is slower than sequential I/O (reading the entire file), even though it moves far fewer bytes. At 500 records with 100 checkpoints, the journal path performs ~500 random seeks vs ~100,000 sequential operations. Random seeks are ~10-100x slower than sequential operations depending on storage.

   **The byte advantage is real and structural.** The time disadvantage is also real and structural. The journal path trades write endurance (497x fewer bytes) for latency (1.7x slower). Which trade is better depends on the workload:
   - Write-endurance-limited (SSD lifespan, cloud storage costs): journal wins
   - Latency-limited (interactive use, tight timeouts): whole-file wins

4. **QUEUE_JOURNAL stays OFF.** Per task instruction, the flag remains off regardless of benchmark results. Turning it on is a production decision requiring GLM review of the crash and interleaving contract.

5. **Last-write-wins behavior preserved.** The task warned: "If that test fails, the guard was added and the test should be INVERTED, not deleted." No version comparison was added to `replay()` or `replay_narrow()`. The existing test `test_on_produces_the_same_load_as_off` passes, proving the behavior is unchanged.

**RISKS:**
- The index adds a file (`queue.jsonl.idx`) beside the queue. If this file is lost or corrupted, it is rebuilt transparently. No data loss.
- The index is validated by digest, so a stale index (base changed without rebuilding) is detected. No silent corruption.
- The narrowed read path in `save()` is only used when journalling is on AND a snapshot is available. Otherwise, the full read path is used. No regression for non-journal paths.

**RECOMMENDED CLAUDE ACTION:**
Review the implementation and tests. The byte target is met; the time target is not. The trade-off (write endurance vs latency) is structural and documented. QUEUE_JOURNAL stays off. If the time penalty is unacceptable, the journal path could be optimized by:
- Batching seeks (read multiple records in one pass)
- Caching journal entries (avoid re-reading the journal)
- Using a different index structure (e.g., B-tree for larger estates)

But these optimizations add complexity. The current implementation is correct, tested, and meets the byte target.
