# GLM adversarial review - storage

2026-09-17T18:09:01.756618+00:00. One call per function.

A SECOND OPINION, NOT A VERDICT. Every line below is a lead to check against the code and the tests by hand.

---

## store.save

`glm-5.3`, 95.199s, usage {'prompt_tokens': 1376, 'completion_tokens': 6000, 'total_tokens': 7376, 'reasoning_tokens': 5730, 'cached_tokens': 1344}.

**1. Arithmetic** (31.8 KB/record measured; merge affects *content*, not write granularity — `_write(recs)` is still whole-file, and every checkpoint also does a full `read_jsonl` under the lock).

- **5,000 records:** file = 159 MB. Held: 159 MB working set + ~159 MB Snapshot copies ("carries what each row was when it was read") + ~159 MB `on_disk` transiently per checkpoint → ~475–640 MB peak, whole run. Writes: 1,000 checkpoints × 159 MB = **159 GB written + 159 GB re-read per pass**.
- **100,000 records:** file = 3.18 GB. Held: ~3.18 GB + ~3.18 GB snapshot + ~3.18 GB transient → **~9.5–13 GB peak per process**, and the docstring's own history describes two writers alive concurrently. Writes: 20,000 × 3.18 GB = **63.6 TB written + 63.6 TB read per pass**. At 2 GB/s sustained, ~9 hours of pure writing; JSON parse of 3.18 GB per checkpoint (~20–60 s) dominates and is also under the lock.
-

## store.load

`glm-5.3`, 89.316s, usage {'prompt_tokens': 358, 'completion_tokens': 6000, 'total_tokens': 6358, 'reasoning_tokens': 5216, 'cached_tokens': 320}.

**1. Arithmetic** (31,790 B/record measured; write model = full-file rewrite per checkpoint, N/5 checkpoints per pass)

| | 5,000 records | 100,000 records |
|---|---|---|
| File size / floor of `Snapshot` in memory | 158,952,600 B ≈ **159 MB** | 3,179,052,000 B ≈ **3.18 GB** |
| Full-file writes per stage pass | 5,000/5 = **1,000** | 100,000/5 = **20,000** |
| Bytes written per stage pass | 1,000 × 159 MB = **159 GB** | 20,000 × 3.18 GB = **63.6 TB** |

- Write amplification per checkpoint: logical delta = 5 records = 159 KB; physical write = full file → **1,000× at 5k, 20,000× at 100k** (amplification grows linearly in N; total is O(N²) = N² × 6.36 KB).
- Wall-clock floor at 1 GB/s sequential SSD, ignoring fsync: **~2.7 min** (5k) and **~17.7 hours per stage pass** (100k). With fsync per checkpoint, worse.
- The 1M target: 31.8 GB file, 200,000 writes, **6.36 PB** per pass — ~74 days of pure writing.
- Memory is a floor from bytes only; parsed Python objects typically run 3–5× the text (~0.5–0.8 GB at 5k; ~10–16 GB at 100k — likely OOM on a 16 GB worker). Labeled estimate; the 159 MB / 3.18 GB floors are fact.
- All repo benchmarks are understated by **31.8/4.2 = 7.57×** on every size-derived number.
- Cohort keying: every record in a second cohort re-pays full evidence price — cost scales with (cohorts × records), no reuse. Mechanism is fact; I have no overlap rate to put a dollar figure on it.

**2. Largest benefit/risk change:** checkpoint interval 5 → 200 (or time-based, e.g. every 5 min). One line. Bytes written drop 40×: 63.6 TB → 1.6 TB at 100k; 17.7 h → 26 min. Risk is bounded and priced: a crash redoes ≤199 records of evidence (if evidence is $0.10/record, worst case $20/crash) — trivial against 62 TB avoided. It does not fix the O(N²) shape; it divides it by 40.

**3. Correctness/concurrency:** **NO FINDING on the code shown.** `load()` is a pure read of one path; no shared mutable state, no lock ordering, no defect provable from it. The three hazards you name depend on code not shown, so I will not assert them — only the falsifiable interleavings to test:
- *Crash mid-write (only if checkpoint writes in place):* checkpoint k does `open(path,'w')` → 17.4 MB truncates to 0 → SIGKILL at byte 8M → next `load()` parses a file with a cut last line → either a parse exception (halt) or 549 records (silent loss of a paid record).
- *Two writers (only if >1 process checkpoints):* A truncates, B truncates, A writes full snapshot, B writes at


---

## CLAUDE VERIFICATION, 2026-09-17

**THE ARITHMETIC IS ACCEPTED.** It agrees with the handoff's own measurement -
31,791 bytes per record over 550 records - and it extends it correctly: the
write model is a full-file rewrite per checkpoint at an interval of 5 records,
so bytes written per stage pass grow as O(N^2). 159 GB per pass at 5,000
records; 63.6 TB at 100,000. **Every size-derived benchmark in this repository
is understated by 7.57x**, because they were computed against an assumed
4.2 KB per record.

**THE HEADLINE RECOMMENDATION IS REJECTED AS STATED.** GLM proposes raising
the checkpoint interval from 5 to 200 - "one line", bytes down 40x, and it
prices the risk at 199 records of re-done evidence per crash.

The arithmetic is right and the trade runs against a lesson this repository
learned the expensive way. `generate.run`'s checkpoint-per-record exists
because a run across eighteen records died fifty minutes in and wrote nothing,
after every model call had been paid for - the comment is in the source. The
direction of travel here has been toward MORE durability, not less, and
"$20 per crash" is a guess at a price nobody has measured.

**What IS accepted is GLM's own aside**: raising the interval "does not fix
the O(N^2) shape; it divides it by 40". The shape is the defect. The fix is
incremental persistence - appending what changed instead of rewriting what did
not - which keeps the durability property AND removes the amplification,
rather than trading one for the other. That is P5 in the handoff's priority
list and it now has a number attached to it.

**NO FINDING on `load()` is accepted as offered** - GLM declined to assert the
three hazards it could not construct from the source it was shown, and named
the falsifiable interleavings instead. That is the right behaviour from this
tool and both interleavings are worth a test.

**One thing to fix in the tool, not the finding:** both calls returned
`completion_tokens: 6000` against a 6,000 cap, with 5,730 and 5,216 of those
spent on reasoning. The answers are truncated mid-sentence. Raise
`--max-tokens` for this target before re-running.
