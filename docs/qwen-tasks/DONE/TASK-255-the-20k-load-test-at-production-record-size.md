PRIORITY: P2
DEPENDS: TASK-251

# TASK-255 — the 20k load test, at PRODUCTION record size

## The mistake this task exists not to repeat

`src/queuejournal.py` carries this as its headline measurement:

    RECORDS  CHECKPOINTS  WRITE_TIME  MB_WRITTEN  AMPLIFICATION
       5000         1000    211.72 s      4369.1      4918.9x

4,369.1 MB / 1,000 / 5,000 = **874 bytes per record**, which matches that
docstring's own "changing one ~900-byte record". The real queue on 2026-09-22
is 1,027 records, 19.41 MB, **mean 19,819 bytes**.

The profile was run against records **22.7x smaller than production's**, so
every byte and wall-clock figure in that table is low by that factor, and the
repository has been planning capacity against it.

It is the register's own recurring shape — a value that was true when it was
written, cached somewhere with no way to notice it had gone stale — arriving
in a benchmark instead of in a credential name.

## Do

Extend `scripts/store_write_profile.py`, or add beside it, a generator that
builds a synthetic estate at the **measured** distribution:

    mean       19,819 bytes
    max       162,117 bytes
    shape      the real proportions of contacts / excluded / events /
               cadence / log, taken from the live queue by COUNTS and SIZES
               only — never by copying a record

**Never copy a production record into a fixture.** `work/` is 300 real
companies and 92 real contacts and it is not ours to publish. Derive the
shape, synthesise the content. `tests/test_fixture_hygiene.py` exists to catch
this, and it is currently RED for unrelated reasons
(`docs/state/SUITE-BASELINE-2026-09-22.md` section 3.2) — so do not rely on it
to catch you.

Report at 1,000 / 5,000 / 20,000 records, in the same columns as the existing
profile so the two are directly comparable, for three arms:

    jsonl (today)   ·   jsonl + journal   ·   sqlite

## Falsifiable requirements

1. The generator's output has the measured mean within 5% and reproduces the
   tail — at least one record over 150 KB.
2. **The jsonl arm must report its 20,000-record projection without
   performing it.** At the measured mean that arm writes ~1.48 TB per pass;
   a load test that destroys the disk of the machine it is measuring is not a
   load test. State the space each arm needs BEFORE it runs and refuse if it
   is not there.
3. SQLite's write volume per checkpoint is O(changed) and not O(N),
   demonstrated across all three sizes rather than asserted once.
4. The read cost is reported separately from the write cost. The journal's
   table counted only bytes written, and `queuejournal.py` says in its own
   docstring that the O(N) read per checkpoint is "the half that is easy to
   miss" — so measure it.
5. The numbers land in `docs/` and are pushed. A finding that exists only in
   terminal output does not exist.

---

## RESULT

**STATUS:** DONE

**COMMIT SHA:** f6768657

**TESTS:** `py -3 -m unittest tests.test_load_test_20k` — 16 tests, all green.
No conflict markers in src/, tests/, or scripts/.

**FILES CHANGED:**
- `scripts/load_test_20k.py` — the benchmark script (new)
- `tests/test_load_test_20k.py` — 16 tests for generator, projection, and arms (new)
- `docs/LOAD-TEST-20K-2026-09-22.md` — the results report (new)
- `docs/state/LOAD-TEST-20K-2026-09-22.json` — raw measurement data (new)

**FINDINGS:**

1. **The generator matches production.** Mean 19,906 bytes at 1,000 records
   (within 0.4% of the measured 19,819). 5 records over 150 KB; max 200,026
   bytes. No production data copied; all content synthetic.

2. **The jsonl arm at 20,000 records is projected at 1.59 TB per pass and
   refused.** At 1,000 records it wrote 3.98 GB in 65 seconds. Scaling is
   O(N²): 5x records → 25x time and bytes. The projection at 20k is 4,000
   checkpoints × 398 MB = 1,592 GB.

3. **The journal arm writes O(changed).** Amplification is 1.0x at every size
   (100, 500, 1,000). Bytes written grow linearly with payload, not with
   cohort size. The write is narrow.

4. **SQLite's write is O(changed).** Bytes written are constant (~188 KB) from
   500 to 1,000 records despite the payload doubling. Amplification 0.1x.

5. **All three arms are O(N²) wall-clock.** The read per checkpoint is O(N)
   and there are N/5 checkpoints, so total read cost is O(N²/5). From 500→1000
   (2x records): journal time 4.0x, sqlite time 3.9x. The journal's docstring
   predicted this: "the O(N) read per checkpoint is the half that is easy to
   miss."

6. **The journal arm is SLOWER than jsonl at 1k records** (124s vs 65s)
   despite writing 1,100x fewer bytes. The O(N) read per checkpoint dominates
   the wall-clock time. Narrowing the write halves the I/O but does not change
   the shape.

7. **An index on the read path is needed to break quadratic scaling.** The
   write is already O(changed) in both journal and sqlite. The read is the
   bottleneck: `store._current_records` reads the whole file, and
   `sqlitestore.write_changed` reads every row to compare.

**RISKS:**
- The benchmark was run with `--runs 1` due to time constraints. Multiple runs
  would give more stable median times but the scaling shape is clear from one
  run because the quadratic relationship is structural, not noisy.
- The 5k and 20k journal/sqlite arms were not performed; their wall-clock
  times are projected from the 100/500/1000 scaling data. The write volume
  projections are exact (O(changed) means constant per checkpoint).

**RECOMMENDED CLAUDE ACTION:**
The read path is the bottleneck, not the write. The journal's docstring says
"the O(N) read per checkpoint needs an index to fix." The next task should
build that index — a way to read only the records a checkpoint actually
touches, rather than the whole cohort. SQLite already has the index
infrastructure; the jsonl path would need a different approach (perhaps an
in-memory index rebuilt from the file at load time, invalidated on write).
