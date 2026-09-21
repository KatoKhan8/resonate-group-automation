#!/usr/bin/env python3
"""The nightly sourcing candidate list. Accumulating, de-duplicated by domain.

TASK-245: the pipeline STOPS here. Candidates accumulate and are exported
weekly for Productive approval. Nothing is spent on them until approved.

A candidate is a company that passed sourcing -> ICP -> MX -> collision and
is waiting for the weekly export. Each row records WHEN and WHY it arrived.

  python -m src.candidatelist list
  python -m src.candidatelist stats
"""
import datetime
import json
import os

from . import store

CANDIDATE_STATES = ("new", "exported", "approved", "rejected")


def candidates_path():
    """Where the candidate list lives. Overridable for tests."""
    return os.path.abspath(os.environ.get("CANDIDATES")
                           or os.path.join(os.path.dirname(store.queue_path()),
                                           "candidates.jsonl"))


def load():
    """Every candidate row, in file order."""
    path = candidates_path()
    if not os.path.exists(path):
        return []
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except (ValueError, TypeError):
                continue
    return rows


def _domain_index(rows):
    """Domain -> row for fast de-duplication."""
    idx = {}
    for row in rows:
        domain = str(row.get("domain") or "").strip().lower()
        if domain:
            idx[domain] = row
    return idx


def append(candidate):
    """Add a candidate if its domain is not already present.

    Returns True if appended, False if the domain already exists.
    A rejected-then-resourced domain does NOT reappear as new.
    """
    domain = str(candidate.get("domain") or "").strip().lower()
    if not domain:
        return False
    rows = load()
    existing = _domain_index(rows)
    if domain in existing:
        return False
    candidate["domain"] = domain
    if "added_at" not in candidate:
        candidate["added_at"] = store.now()
    if "state" not in candidate:
        candidate["state"] = "new"
    path = candidates_path()
    store.refuse_production_write(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(candidate, sort_keys=True) + "\n")
    return True


def mark_exported(domains, when=None):
    """Mark a batch of domains as exported. when defaults to now."""
    when = when or store.now()
    rows = load()
    domain_set = {str(d).strip().lower() for d in domains}
    changed = 0
    for row in rows:
        d = str(row.get("domain") or "").strip().lower()
        if d in domain_set and row.get("state") == "new":
            row["state"] = "exported"
            row["exported_at"] = when
            changed += 1
    if changed:
        _rewrite(rows)
    return changed


def update(domain, **fields):
    """Update fields on one candidate by domain."""
    domain = str(domain or "").strip().lower()
    if not domain:
        return False
    rows = load()
    for row in rows:
        if str(row.get("domain") or "").strip().lower() == domain:
            row.update(fields)
            _rewrite(rows)
            return True
    return False


def _rewrite(rows):
    """Atomically rewrite the candidate file."""
    path = candidates_path()
    store.refuse_production_write(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")
    os.replace(tmp, path)


def stats():
    """Counts by state."""
    rows = load()
    counts = {}
    for row in rows:
        s = row.get("state", "new")
        counts[s] = counts.get(s, 0) + 1
    return {"total": len(rows), "by_state": counts}


def domains_already_known():
    """Every domain on the list, for the sourcing diff."""
    return {str(r.get("domain") or "").strip().lower()
            for r in load() if r.get("domain")}


def main(argv=None):
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd")
    sub.add_parser("list")
    sub.add_parser("stats")
    a = p.parse_args(argv)
    if a.cmd == "stats":
        print(json.dumps(stats(), indent=2))
    else:
        for row in load():
            print(json.dumps(row, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
