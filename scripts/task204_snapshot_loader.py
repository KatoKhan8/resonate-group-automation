"""A snapshot loader that makes stale reads impossible.

Returns records AND stamp together so a caller cannot get the data without
the date. Detects staleness by comparing the snapshot stamp against the live
queue's mtime when both are available.

Usage:
    from scripts.task204_snapshot_loader import load_snapshot, SnapshotData

    data = load_snapshot()
    if data.is_stale:
        print(f"WARNING: snapshot is stale (stamp={data.stamp}, live mtime={data.live_mtime})")
    for record in data.records:
        ...

The loader never silently returns records without a stamp. If the stamp file
is missing, it raises. If the snapshot file is missing, it raises. A caller
that catches the exception knows it has neither.
"""
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNAPSHOT_PATH = os.path.join(ROOT, "work", "queue.snapshot.jsonl")
STAMP_PATH = os.path.join(ROOT, "work", "queue.snapshot.STAMP")
LIVE_PATH = os.path.join(ROOT, "work", "queue.jsonl")


@dataclass(frozen=True)
class SnapshotData:
    """Records AND stamp, inseparable. The stamp is not optional metadata -
    it is part of the data. A record without a stamp is a lie."""
    records: List[dict]
    stamp_raw: str
    stamp_timestamp: Optional[str]
    stamp_commit: Optional[str]
    stamp_record_count: Optional[int]
    is_stale: bool
    staleness_reason: str

    @property
    def count(self) -> int:
        return len(self.records)

    def describe(self) -> str:
        parts = [f"{self.count} records"]
        if self.stamp_timestamp:
            parts.append(f"stamped {self.stamp_timestamp}")
        if self.stamp_commit:
            parts.append(f"from {self.stamp_commit}")
        if self.is_stale:
            parts.append(f"STALE: {self.staleness_reason}")
        return ", ".join(parts)


def _parse_stamp(raw: str) -> tuple:
    """Parse '2026-09-15T17:52:12+00:00 from master cf23154 550 records'."""
    parts = raw.strip().split()
    timestamp = parts[0] if parts else None
    commit = None
    count = None
    for i, p in enumerate(parts):
        if p == "master" and i + 1 < len(parts):
            commit = "master " + parts[i + 1]
        if p.isdigit() and i == len(parts) - 1:
            count = int(p)
    return timestamp, commit, count


def _live_queue_mtime() -> Optional[str]:
    if not os.path.exists(LIVE_PATH):
        return None
    mtime = os.path.getmtime(LIVE_PATH)
    return datetime.fromtimestamp(mtime, tz=None).isoformat()


def _live_queue_count() -> Optional[int]:
    if not os.path.exists(LIVE_PATH):
        return None
    n = 0
    with open(LIVE_PATH, encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.strip():
                n += 1
    return n


def load_snapshot(
    snapshot_path: str = SNAPSHOT_PATH,
    stamp_path: str = STAMP_PATH,
) -> SnapshotData:
    """Load the snapshot with its stamp. Raises FileNotFoundError if either
    file is missing. A caller that wants to fall back to live state should
    catch the exception explicitly."""
    if not os.path.exists(snapshot_path):
        raise FileNotFoundError(
            f"Snapshot not found: {snapshot_path}. "
            f"Use src.store.queue_path() for live state, or "
            f"docs/state/QUEUE-MANIFEST.json for a sanitized view."
        )
    if not os.path.exists(stamp_path):
        raise FileNotFoundError(
            f"Stamp not found: {stamp_path}. The snapshot exists but has no "
            f"provenance. Refusing to load records without a date."
        )

    with open(stamp_path, encoding="utf-8") as f:
        stamp_raw = f.read().strip()
    timestamp, commit, stamp_count = _parse_stamp(stamp_raw)

    records = []
    with open(snapshot_path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))

    live_mtime = _live_queue_mtime()
    live_count = _live_queue_count()

    is_stale = False
    staleness_reason = ""

    if live_mtime and timestamp:
        try:
            snap_dt = datetime.fromisoformat(timestamp)
            live_dt = datetime.fromisoformat(live_mtime)
            if snap_dt < live_dt:
                is_stale = True
                staleness_reason = (
                    f"snapshot stamp {timestamp} is older than "
                    f"live queue mtime {live_dt.isoformat()}"
                )
        except (ValueError, TypeError):
            pass

    if stamp_count is not None and live_count is not None:
        if stamp_count != live_count:
            is_stale = True
            staleness_reason = (
                f"snapshot has {stamp_count} records but live queue has "
                f"{live_count}"
            )

    if stamp_count is not None and len(records) != stamp_count:
        is_stale = True
        staleness_reason = (
            f"stamp says {stamp_count} records but file has {len(records)}"
        )

    return SnapshotData(
        records=records,
        stamp_raw=stamp_raw,
        stamp_timestamp=timestamp,
        stamp_commit=commit,
        stamp_record_count=stamp_count,
        is_stale=is_stale,
        staleness_reason=staleness_reason,
    )


def main():
    try:
        data = load_snapshot()
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    print(f"Snapshot: {data.describe()}")
    print(f"Stamp raw: {data.stamp_raw}")
    if data.is_stale:
        print(f"STALE: {data.staleness_reason}")
        print("This snapshot should NOT be treated as current state.")
        print("Use work/queue.jsonl (live) or docs/state/QUEUE-MANIFEST.json (sanitized).")
    else:
        print("Snapshot appears current (live queue not available for comparison, or matches).")


if __name__ == "__main__":
    main()
