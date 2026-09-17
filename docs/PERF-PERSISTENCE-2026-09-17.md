# Persistence is the first bottleneck, and it is quadratic. Measured.

Measured 2026-09-17 with `scripts/store_write_profile.py`. Synthetic records
in a temp directory: no network, no provider, no real estate, no PII. Every
byte figure is the real size of a file on disk at the moment it was written,
not `len(json.dumps(...))` of the record in memory.

## The numbers

    RECORDS  QUEUE_KB  CHECKPOINTS  WRITE_TIME  MB_WRITTEN  AMPLIFICATION
         50      44.5           10      0.13 s         0.4          49.3x
        500     446.0          100      3.40 s        43.6         492.4x
       5000    4465.2         1000    211.72 s      4369.1        4918.9x

Scaling:

    50   -> 500 :  records x10,  time x25.4,  bytes x100.2
    500  -> 5000:  records x10,  time x62.4,  bytes x100.2
    50   -> 5000:  records x100, time x1580,  bytes x10000

Bytes scale as the SQUARE of the cohort, exactly and at both steps. Time is
worse than the bytes at the top end, which is the filesystem rather than the
serialiser.

**Write amplification equals cohort size**, because that is literally what it
is: changing one ~900-byte record rewrites every record in the file. At 5,000
records one changed record costs 4.4 MB of disk write.

## What this means for the target operating model

The requirement is that 500 leads be a routine batch and 5,000 a normal
resumable workload.

    500  records: 3.4 seconds and 44 MB of persistence   — a rounding error
    5000 records: 3.5 MINUTES and 4.4 GIGABYTES           — not a workload

And that 3.5 minutes contains **no provider latency whatsoever**. It is pure
local disk, spent before a single enrichment call has been waited on. It is
also 4.4 GB of write endurance per pass, which is a hardware cost as well as
a time one.

**This is the number one bottleneck at the target scale.** It is not close.

## Why, precisely

`store._write` serialises every record to a temp file and renames it. That
rename is what makes the write atomic and a crash leave the previous queue
intact, which is a property worth keeping. `run.CHECKPOINT_EVERY` is 5, so a
pass over N records performs N/5 of those whole-file writes, each costing
O(N). Total O(N^2/5).

## What NOT to do

**Raising `CHECKPOINT_EVERY` is not the fix and has already been rejected
once** (GLM's proposal of 5 -> 200, rejected 2026-09-17). It divides the
constant and leaves the shape: 5,000 records at interval 200 still writes
109 MB and is still quadratic, and it trades directly against the lesson that
put checkpoint-per-five-records there — `store.save`'s own docstring records
a reproduced incident where a wider window lost a reply, an unsubscribe, a
drop reason and three purchased decision-makers.

The checkpoint interval is a durability decision. It must not be relitigated
as a performance one.

## The shape a fix has to have

One record changing should cost about one record's worth of write. That means
the base file stops being rewritten per checkpoint — an append-only journal of
record deltas, replayed over the base on load, compacted on a schedule or a
size ratio.

Everything below is currently load-bearing in `store.save` and a journal has
to preserve all of it, which is why this is a design note and not a patch:

- **Atomicity.** A crash mid-write must leave a readable queue. Append + flush
  is atomic per line in a way a truncating rewrite is not, but a torn final
  line has to be detected and discarded on replay rather than parsed.
- **The `Snapshot` merge.** `save` is already not a total write when `recs`
  came from `load`: absent rows are kept, unchanged rows keep the disk
  version, and only rows this caller actually changed are applied. A journal
  makes this *easier* — a delta is exactly "what this caller changed" — but
  the merge rules must come out identical.
- **`expect_digest` optimistic concurrency.** The digest is of the whole file
  today. A journal needs an equivalent that a second process cannot race.
- **`refuse_evidence_loss`.** Paid verification evidence must not be droppable
  by a write. It indexes per record, so it survives a per-record delta, but
  the guard has to run on the delta path and not only on compaction.
- **Backward compatibility.** `work/queue.jsonl` must stay readable by
  anything that reads it today, including a fresh clone with no journal.

## Rank among the ten hypotheses

    1  queue.jsonl full-file rewrite        CONFIRMED. 4919x at 5000. #1.
    2  excessive checkpoint frequency       CONFIRMED as a multiplier of #1,
                                            and explicitly NOT the thing to
                                            change. Same root cause.
    5  evidence keyed to record_id          REFUTED AS STATED. See below.
    3,4,6,7,8,9,10                          NOT YET MEASURED. TASK-220.

### Hypothesis 5, corrected

`evidence.evidence_id` does hash `record_id` into its material while its
docstring claims the id derives from what the evidence *is*. That docstring is
wrong and the coupling is real.

**But it costs nothing, because nothing reuses evidence by that id.** Every
consumer — `dossier`, `eligibility`, `audit`, `icp`, `outcomes` — uses it as
an INTRA-record reference: which evidence this record's draft selected, which
evidence an outcome is attributed to. There is no cross-record lookup keyed
on it, so restabilising it would not save one provider call. Fixing the
docstring is worth doing; expecting a cost saving from it is not.

**The real cross-cohort waste is next door.** `research._crawl_cache` is an
in-memory dict cleared at the start of every `enrich.run()` pass, so a company
crawled for cohort A is crawled again for cohort B. Its identity model is
already right — `crawl_cache_set` stores the evidence with `record_id=None`
and the read path re-stamps the current record id on reuse, which is exactly
the stable-subject-key shape that was proposed as new work. It simply does not
survive the pass.

So the cross-cohort reuse fix is "persist this cache under its existing
semantics, with the per-field TTL `research` already implements", not "rework
evidence identity". That is a much smaller change than the hypothesis implied.
Its hit rate is being measured before anything is built on it.

---

## UPDATE 2026-09-18: the journal is wired, and it is NOT a clean win

`QUEUE_JOURNAL=1`, same harness, 5,000 records and 1,000 checkpoints:

    PATH              BYTES WRITTEN   AMPLIFICATION   WALL TIME
    whole-file (off)      4,369 MB         4918.9x      211.7 s
    journal    (on)           1.0 MB          1.1x      262.3 s

**Writes fall by a factor of 4,369. Wall time gets 24% WORSE.**

Both numbers are real and the second one is the one to act on. The journal
removes the quadratic WRITE and leaves the O(N) READ - and then makes that
read slightly worse, because `save` must now read the base file AND replay a
journal that grows all pass. At 1,000 checkpoints that costs more than the
writes it saved.

So the honest status is: **the shape is fixed, the bottleneck moved.**

### What it is nonetheless worth

- 4.4 GB per pass becomes 1 MB. That is write endurance on an SSD, and it is
  transfer volume on anything synced or networked, neither of which shows up
  in a wall clock.
- One changed record costs 1.0 KB instead of 4.4 MB. The amplification is
  1.1x, which is as close to optimal as this gets.
- It is the precondition for fixing the read. While every checkpoint rewrote
  the file, an index over the base was pointless.

### What it does NOT do, and what comes next

It does not make 5,000 records a comfortable workload on its own. The
remaining cost is the full read per checkpoint, for the digest and the two
loss guards, and narrowing that needs an INDEX - offsets per record id, so a
guard can read the rows a delta touches instead of all of them. That is a
larger change than this one and it is not started.

**The flag stays OFF by default until the read is fixed too.** Turning it on
today trades 4.4 GB of writes for 50 seconds, and which of those matters
depends on a constraint nobody has stated yet. It is wired, tested and
measured so that the decision can be made on numbers rather than on
architecture.

---

## CORRECTION 2026-09-18: every byte figure above was 37x too small

GLM's storage review checked the arithmetic against the REAL estate and it
does not match what this benchmark was measuring. Verified:

    work/queue.jsonl   17,486,311 bytes over 550 records = 31,793 B/record
    synthetic record used by store_write_profile.py       =    859 B/record
    UNDERSTATEMENT                                              37.0x

The synthetic record carried a name, a domain, two contacts and a short
summary. A real record carries what enrichment PUTS in it - provider answers,
crawl evidence, timelines, verification history - and that is what makes it
31.8 KB. The benchmark was measuring a record shape that does not exist.

`_record()` now pads to the measured size and the size is a named constant
with its provenance. The padding is synthetic filler: what is taken from the
estate is the SIZE and nothing else - no company, no contact, no address.

### Re-measured at the real record size, 500 records

    PATH              BYTES WRITTEN   AMPLIFICATION   WALL TIME
    whole-file (off)      1,517 MB          499.8x       13.3 s
    journal    (on)           3.0 MB          1.0x       22.4 s

**506x fewer bytes. 69% slower.** The time penalty is WORSE with real-sized
records than with the toy ones, because the O(N) read-and-replay that
journalling leaves in place is itself proportional to record size.

### 5,000 records: MODELLED, not measured, and why

    whole-file    ~159 GB written per pass
    journal         ~30 MB written per pass

**This one is deliberately not measured.** Writing 159 GB to the operator's
SSD to confirm a number that two measured points and a proven-quadratic
scaling law already give is a real hardware cost for no new information. The
model is the measured 500-record figure scaled by the measured quadratic, and
it agrees with the independent arithmetic (5,000 x 31,793 B = 159 MB per
whole-file write, x 1,000 checkpoints = 159 GB).

Anything reported as 4.4 GB earlier in this document is the 859-byte record.
**The real figure is ~159 GB per pass.**

### What the correction changes

It does not change the RANKING - persistence was the number one bottleneck at
4.4 GB and is more so at 159 GB. It changes two things:

1. **The journal is worth far more than it looked.** 159 GB to 30 MB per pass
   is not a tuning gain, it is the difference between a pass that is safe to
   run repeatedly and one that is not.
2. **The read is now unambiguously the thing to fix.** 69% slower on real
   records, and the whole penalty is the O(N) read-and-replay. An index over
   the base is no longer a nice-to-have.

### GLM's own recommendation, rejected again and for a new reason

It proposed `CHECKPOINT_EVERY` 5 -> 100 or 5 -> 500 as the highest
benefit/risk change. Rejected, as on 2026-09-17: the interval is a durability
decision and `store.save`'s docstring records a reproduced incident where a
wider window lost a reply, an unsubscribe, a drop reason and three purchased
decision-makers.

But its accompanying observation is sharp and worth keeping: *"durability is
unchanged IF deltas are journalled per-record between checkpoints."* That
points at a real design - separate the cheap DURABILITY append, which can
happen per record, from the expensive CONSISTENCY pass that reads, merges and
runs both loss guards. **It is not safe to adopt as stated**, because the loss
guards are what protect against a concurrent writer and running them a
hundred times less often widens exactly that window. Recorded as a lead, not
a plan.
