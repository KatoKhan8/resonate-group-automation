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
