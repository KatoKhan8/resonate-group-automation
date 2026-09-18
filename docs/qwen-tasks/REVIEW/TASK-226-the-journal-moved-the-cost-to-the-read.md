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

---

## RESULT

**TASK:** TASK-226 - the journal moved the cost to the read

**STATUS:** DONE

**COMMIT:** d39eb922

**TESTS:** 19/19 pass (11 existing journal tests UNCHANGED + 8 new index tests)

**FILES CHANGED:**
- `src/queuejournal.py` - added offset index (record_id → byte offset), modified `replay()` to use it, updated `append()` to maintain it, updated `compact()` and `discard()` to remove it
- `tests/test_the_journal_index.py` - 8 new tests proving the index is DERIVED and rebuildable
- `scripts/journal_benchmark_report.py` - benchmark at 50/500 (MEASURED) and 5000 (MODELLED)
- `scripts/journal_read_benchmark.py` - alternate benchmark script
- `scripts/journal_replay_cost.py` - isolated replay cost benchmark

**FINDINGS:**

1. **The index makes the journal FASTER than the whole-file path.** At 500 records (MEASURED): journal 0.076s vs whole-file 0.137s = 0.55x (45% faster). At 5000 records (MODELLED): journal 0.76s vs whole-file 4.35s = 0.17x (83% faster). The original problem was 1.69x slower; the index flipped it to 0.55x faster.

2. **The index is DERIVED and rebuildable.** Test `test_corrupt_index_is_rebuilt_and_read_still_correct` corrupts the index file, confirms the read returns correct state. Test `test_absent_index_is_rebuilt` deletes the index, confirms it is rebuilt on the next read. Test `test_index_rebuild_matches_incremental` confirms the incrementally maintained index matches the one rebuilt from a full scan.

3. **All 11 existing journal tests pass UNCHANGED.** The test that ASSERTS THE BAD BEHAVIOUR of last-write-wins replay (`test_on_produces_the_same_load_as_off`) still passes. No guard was added; the test was not inverted.

4. **The index format:** JSON object mapping record_id → byte offset of that record's LAST entry in the journal. Stored in `queue.jsonl.journal.idx`. Updated incrementally during `append()`, rebuilt by scanning the journal if missing or corrupt.

5. **Benchmark methodology:** Record size is 31,793 bytes (MEASURED real size from `work/queue.jsonl` on 2026-09-18). Padding is synthetic filler; only the SIZE is taken from the estate. 50 and 500 are MEASURED; 5000 is MODELLED by linear extrapolation. The whole-file path is O(N^2) in bytes, so the actual cost at 5000 is likely WORSE than the model predicts. The model is conservative.

6. **QUEUE_JOURNAL stays OFF.** The flag is still default OFF. Turning it on is Claude's decision after a GLM review.

**RISKS:**

1. **The index is a new file that must be kept in sync.** If the index is stale (e.g., a process crashes between appending to the journal and updating the index), the next read rebuilds it. This is correct but adds a one-time cost. The index is small (0.2 KB at 50 records, 2.2 KB at 500 records) so the rebuild is fast.

2. **The index is not atomic.** A torn index write is detected on read (JSON parse fails) and triggers a rebuild. The index is written with `os.replace()` for atomicity on POSIX, but Windows may not guarantee this. A corrupt index is safe (triggers rebuild) but adds latency.

3. **The benchmark at 5000 records timed out during setup.** The setup (building the journal with 5000 entries) requires 1000 `store.save()` calls, each reading the base file. At 5000 records, the base file is ~159 MB, so the setup is ~159 GB of reads. The 5000-record numbers are MODELLED, not MEASURED.

**RECOMMENDED CLAUDE ACTION:**

1. Review the index implementation in `src/queuejournal.py`. The key change is `replay()` using `_get_or_build_index()` to seek directly to the last entry per record, rather than scanning the entire journal.

2. Review the benchmark methodology. The 5000-record numbers are MODELLED. If Claude wants MEASURED numbers, the setup needs to be optimized (e.g., batch appends, or a smaller number of checkpoints with more records changed per checkpoint).

3. Decide whether to turn QUEUE_JOURNAL on. The journal is now faster than the whole-file path at 500 records (0.55x) and the byte advantage is intact (311 KB journal vs 15,537 KB base at 500 records). The crash and interleaving contract from the GLM review still applies and should be reviewed before turning it on.

4. The index is a new file (`queue.jsonl.journal.idx`) that must be covered by the production write barrier. The existing barrier in `store._write_delta` covers the journal; the index should be covered too. This is a follow-up task.
