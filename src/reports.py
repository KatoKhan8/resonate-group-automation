#!/usr/bin/env python3
"""Report history: what was generated, for whom, by whom, and over what.

A client report is a document that leaves the building. Six months later
somebody asks "what did we tell them in July" - and the answer has to come
from a record rather than from somebody's Downloads folder.

So every generation writes a row here. The row is the *description* of a
report, not the report: no PDF bytes are stored. Two reasons, and the second
is the one that matters:

  * a few hundred kilobytes per generation adds up to a state file nobody can
    read, in a system whose whole storage model is line-per-row JSONL
  * the PDF is a pure function of the data plus the settings, so regenerating
    from the stored row is both possible and more honest - a stored PDF would
    keep looking authoritative long after the numbers behind it had been
    corrected

Rows are append-only in normal use. `record()` appends and `mark()` moves a
row's status; nothing here rewrites what a report said, because the history is
the audit trail and an audit trail somebody can edit is decoration.

Tenancy is by `workspace`, and `for_workspace` is the only listing the web
layer uses for a scoped request.
"""
import os
import uuid

from . import store

# The same env-override shape every other state module uses - `JOBS`,
# `WORKSPACES`, `AUDIT`, `SENDERS`, `NOTIFICATIONS`. `store.use_directory`
# clears all of them together so a test or a demo moves the whole set.
ENV = "REPORTS"

PLANNED = "planned"
GENERATED = "generated"
DOWNLOADED = "downloaded"
FAILED = "failed"
STATUSES = (PLANNED, GENERATED, DOWNLOADED, FAILED)


def path():
    return os.path.abspath(os.environ.get(ENV)
                           or os.path.join(os.path.dirname(store.queue_path()),
                                           "reports.jsonl"))


def load():
    return store.read_jsonl(path())


def save(rows, timeout=None):
    with store.lock(timeout, for_path=path()):
        store.write_jsonl(path(), rows)


def transaction(timeout=None):
    return store.file_transaction(path(), timeout)


def new_id():
    return f"rep-{uuid.uuid4().hex[:10]}"


def record(workspace, template, sections, by, period=None, campaigns=None,
           report_id=None, status=GENERATED, bytes_written=None, error=None,
           at=None):
    """Append one generation. Returns the stored row.

    `sections` is stored as the list that actually rendered, not the list that
    was requested. Those differ whenever a request names a section the
    template does not offer, and the useful record is what the client
    received.
    """
    row = {
        "id": report_id or new_id(),
        "at": at or store.now(),
        "workspace": workspace,
        "template": template,
        "sections": list(sections or []),
        "period": period or "All time",
        "campaigns": list(campaigns or []),
        "by": by,
        "status": status,
        "bytes": bytes_written,
        "error": error,
        "downloads": 0,
    }
    with transaction() as current:
        current.append(row)
    return row


def mark(report_id, status, **changes):
    """Move a row's status. Never rewrites what the report contained."""
    updated = None
    with transaction() as current:
        for index, row in enumerate(current):
            if row.get("id") == report_id:
                updated = {**row, **changes, "status": status}
                if status == DOWNLOADED:
                    updated["downloads"] = (row.get("downloads") or 0) + 1
                current[index] = updated
                break
    return updated


def get(report_id, rows=None):
    for row in (load() if rows is None else rows):
        if row.get("id") == report_id:
            return row
    return None


def for_workspace(workspace, limit=100, rows=None):
    """One workspace's reports, newest first. The only scoped listing.

    A caller that wants every workspace's reports asks `history()`, and the
    only thing that calls it is the super admin's console.
    """
    found = [r for r in (load() if rows is None else rows)
             if r.get("workspace") == workspace]
    return sorted(found, key=lambda r: str(r.get("at")), reverse=True)[:limit]


def history(workspace=None, template=None, limit=200, rows=None):
    found = load() if rows is None else rows
    if workspace:
        found = [r for r in found if r.get("workspace") == workspace]
    if template:
        found = [r for r in found if r.get("template") == template]
    return sorted(found, key=lambda r: str(r.get("at")), reverse=True)[:limit]


def summarise(workspace=None, rows=None):
    found = history(workspace, limit=100000, rows=rows)
    by_status, by_template = {}, {}
    for row in found:
        by_status[row["status"]] = by_status.get(row["status"], 0) + 1
        by_template[row["template"]] = by_template.get(row["template"], 0) + 1
    return {
        "total": len(found),
        "by_status": dict(sorted(by_status.items())),
        "by_template": dict(sorted(by_template.items())),
        "last": found[0] if found else None,
    }
