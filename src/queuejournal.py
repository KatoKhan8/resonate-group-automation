#!/usr/bin/env python3
"""An append-only log of record changes, so a checkpoint stops costing O(N).

## The measurement this exists to answer

`scripts/store_write_profile.py`, run 2026-09-17:

    RECORDS  CHECKPOINTS  WRITE_TIME  MB_WRITTEN  AMPLIFICATION
         50           10      0.13 s         0.4        49.3x
        500          100      3.40 s        43.6       492.4x
       5000         1000    211.72 s      4369.1      4918.9x

`store._write` serialises every record and renames, and `run.CHECKPOINT_EVERY`
is 5, so a pass over N records performs N/5 whole-file writes each costing
O(N). Write amplification equals cohort size because that is literally what it
is: changing one ~900-byte record rewrites the file. At the 5,000-record
target that is three and a half minutes of pure local disk and 4.4 GB, before
one provider call has been waited on.

**This module is NOT WIRED.** `store.save` is untouched. It is the primitive a
wiring change would use, landed separately so that the storage engine and the
change to the only file holding real client state are two reviewable things
rather than one.

## Why a journal rather than a wider checkpoint interval

Raising `run.CHECKPOINT_EVERY` divides the constant and keeps the shape, and
it was already rejected once on 2026-09-17. It also trades against durability,
which is not a trade available here: `store.save`'s docstring records a
reproduced incident where a wider window lost a reply, an unsubscribe, a drop
reason and three purchased decision-makers. **The checkpoint interval is a
durability decision and must not be relitigated as a performance one.** A
journal keeps the interval at five and makes five records cost five records.

## What a checkpoint has to keep being

`store.save` today does six things under the lock, and a delta path has to
preserve every one:

    read on_disk           O(N) - and this is the HALF THAT IS EASY TO MISS.
                           The measurement above counted bytes written; the
                           read is O(N) per checkpoint too, so the real I/O
                           is roughly twice what that table shows.
    digest check           optimistic concurrency against a second process
    Snapshot.merge_onto    absent rows kept, unchanged rows keep the disk
                           version, only this caller's edits applied
    refuse_evidence_loss   paid verification evidence may not be dropped
    refuse_history_loss    events and log lines may not be rewritten
    _write                 atomic: a crash leaves the previous queue readable

A delta preserves them by NARROWING them rather than skipping them: the guards
run against the records the delta actually touches, which is the same
comparison on a smaller set, not a weaker one.

## The format

One JSON object per line, each a complete record plus a header:

    {"seq": 12, "at": "...", "base": "<digest>", "record": {...}}

`base` is the digest of the base file the delta was computed against, so a
journal cannot be replayed onto the wrong base. Later entries for the same
record id win - last write, in file order.

## Crash safety

Append-and-flush, never truncate-and-rewrite, so the previous bytes are
untouched by a failing write. A process dying mid-append can still leave a
torn final line; `replay` discards a trailing line that does not parse and
reports it, rather than raising. **A torn line anywhere but the end is not
recoverable and raises**, because that means something other than a crash
wrote here and guessing which records survived is how a fabricated state gets
believed.
"""
import json
import os

SUFFIX = ".journal"


class JournalCorrupt(RuntimeError):
    """A journal is damaged somewhere other than its final line.

    Raised rather than repaired. A torn tail is a crash and is discardable; a
    torn middle means a second writer, a partial copy or a disk fault, and
    replaying the readable parts would produce a state that never existed.
    """


def path_for(queue_path):
    """The journal beside its queue. One definition, as `store` does it."""
    return queue_path + SUFFIX


def append(queue_path, records, base_digest, at=None):
    """Append one delta per record. Returns the number of entries written.

    Opened in append mode and flushed before returning: the bytes already in
    the file are never rewritten, so a failure here cannot damage earlier
    entries the way a truncating write can.
    """
    records = [r for r in records if r]
    if not records:
        return 0
    journal = path_for(queue_path)
    os.makedirs(os.path.dirname(journal) or ".", exist_ok=True)
    start = _count(journal)
    with open(journal, "a", encoding="utf-8", newline="\n") as handle:
        for offset, record in enumerate(records):
            entry = {"seq": start + offset,
                     "at": at,
                     "base": base_digest,
                     "record": record}
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return len(records)


def _count(journal):
    if not os.path.exists(journal):
        return 0
    with open(journal, encoding="utf-8") as handle:
        return sum(1 for _ in handle)


def read(queue_path, base_digest=None):
    """Every entry, in order. `(entries, torn_tail)`.

    `torn_tail` is True when the last line did not parse and was discarded -
    the signature of a process that died mid-append.
    """
    journal = path_for(queue_path)
    if not os.path.exists(journal):
        return [], False
    with open(journal, encoding="utf-8") as handle:
        lines = handle.read().splitlines()

    entries = []
    torn_tail = False
    for index, line in enumerate(lines):
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except ValueError:
            if index == len(lines) - 1:
                torn_tail = True
                break
            raise JournalCorrupt(
                f"{journal} line {index + 1} of {len(lines)} does not parse, "
                f"and it is not the final line. A torn tail is a crash and is "
                f"discardable; a torn middle is not - something other than a "
                f"crash wrote here, and replaying around it would produce a "
                f"state that never existed")
        if not isinstance(entry, dict) or "record" not in entry:
            raise JournalCorrupt(
                f"{journal} line {index + 1} parsed but carries no `record`. "
                f"A journal entry without a record is not a journal entry")
        entries.append(entry)

    if base_digest is not None:
        wrong = {e.get("base") for e in entries} - {base_digest}
        if wrong:
            raise JournalCorrupt(
                f"{journal} holds entries computed against base digest(s) "
                f"{sorted(wrong)!r} and the base on disk is {base_digest!r}. "
                f"Replaying a delta onto a base it was not computed from is "
                f"how a record reverts to a value nobody wrote")
    return entries, torn_tail


def replay(base_records, queue_path, base_digest=None):
    """Base records with every delta applied. `(records, applied, torn_tail)`.

    Order is preserved for records that were already in the base; records the
    journal introduces are appended in first-seen order. A caller that needs
    a stable order for NEW records gets file order, which is the order they
    were checkpointed in.
    """
    entries, torn_tail = read(queue_path, base_digest)
    if not entries:
        return list(base_records), 0, torn_tail

    latest = {}
    for entry in entries:
        record = entry.get("record") or {}
        rid = record.get("id")
        if rid is None:
            raise JournalCorrupt(
                f"{path_for(queue_path)} seq {entry.get('seq')} holds a "
                f"record with no `id`. A delta that cannot name its record "
                f"cannot be applied to one")
        latest[rid] = record

    out = []
    seen = set()
    for record in base_records:
        rid = record.get("id")
        seen.add(rid)
        out.append(latest.get(rid, record))
    for rid, record in latest.items():
        if rid not in seen:
            out.append(record)
    return out, len(latest), torn_tail


def should_compact(queue_path, ratio=2.0, min_bytes=1_000_000):
    """True when the journal has grown enough to be worth folding in.

    A ratio rather than an entry count, because the cost that matters is the
    bytes `load` has to read, not how many times somebody called `save`.
    `min_bytes` stops a tiny estate compacting constantly: rewriting a 44 KB
    file is not worth avoiding, and the whole point is to not rewrite.
    """
    journal = path_for(queue_path)
    if not os.path.exists(journal):
        return False
    journal_bytes = os.path.getsize(journal)
    if journal_bytes < min_bytes:
        return False
    base_bytes = os.path.getsize(queue_path) if os.path.exists(queue_path) else 0
    if base_bytes == 0:
        return True
    return journal_bytes / base_bytes >= ratio


def discard(queue_path):
    """Remove the journal. ONLY after its contents are in the base file.

    Separate from the compaction write on purpose: the base must be durable
    before the deltas that produced it stop existing, or a crash between the
    two loses them. The caller writes the base, fsyncs, and only then calls
    this.
    """
    journal = path_for(queue_path)
    if os.path.exists(journal):
        os.remove(journal)
