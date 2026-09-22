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
