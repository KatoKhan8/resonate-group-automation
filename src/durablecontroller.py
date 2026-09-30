#!/usr/bin/env python3
"""The minimum durable controller, and nothing more.

Persists only what cannot be derived from the estate:
  - source position          (row in the productive CSV)
  - batch state              (identity, running/complete)
  - provider write/readback  (per enrolled record)

The queue answers everything else. A record that is already QUALIFIED,
enrolled, approved or pushed needs no second entry in this checkpoint.

Duplicate protection is the point: a restart must never re-enrol or re-send
to somebody already staged. Proven by the kill-and-restart test.

Writes go through store.transaction. Provider writes go through
providerwrites.perform / executionscope. No second path is opened.

Dry by default; --live explicit.
"""
import argparse
import csv
import io
import json
import os
import sys
import uuid

from . import store

# --------------------------------------------------------------- checkpoint

CHECKPOINT_VERSION = 1

BATCH_RUNNING = "running"
BATCH_COMPLETE = "complete"
BATCH_STATES = (BATCH_RUNNING, BATCH_COMPLETE)

WRITE_PENDING = "pending"
WRITE_PERFORMED = "performed"
WRITE_READBACK_OK = "readback_ok"
WRITE_FAILED = "failed"
WRITE_STATES = (WRITE_PENDING, WRITE_PERFORMED, WRITE_READBACK_OK, WRITE_FAILED)

DISPOSITION_QUALIFIED = "QUALIFIED"
DISPOSITION_HELD = "HELD"
DISPOSITION_NOT_QUALIFIED = "NOT_QUALIFIED"


def checkpoint_path():
    """Resolved per call, not at import, so tests can point elsewhere."""
    return os.path.abspath(
        os.environ.get("CONTROLLER_CHECKPOINT")
        or os.path.join(os.path.dirname(store.queue_path()),
                        "controller_checkpoint.json"))


def load_checkpoint():
    """The checkpoint, or an empty one if none exists.

    A corrupt checkpoint is treated as absent: the source position resets to
    zero and the batch starts fresh. This is safe because every enrollment is
    idempotent on the record id, and the action ledger refuses a second
    reservation for a key already in flight.
    """
    path = checkpoint_path()
    if not os.path.exists(path):
        return _empty_checkpoint()
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or data.get("version") != CHECKPOINT_VERSION:
            return _empty_checkpoint()
        return data
    except (OSError, ValueError):
        return _empty_checkpoint()


def _empty_checkpoint():
    return {
        "version": CHECKPOINT_VERSION,
        "source_position": 0,
        "batch_id": None,
        "batch_state": None,
        "enrolled": {},
    }


def save_checkpoint(data):
    """Atomic write under the same lock discipline as everything in work/."""
    path = checkpoint_path()
    store.refuse_production_write(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with store.lock(for_path=path):
        tmp = f"{path}.{os.getpid()}.tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, indent=2, sort_keys=True)
        os.replace(tmp, path)


# --------------------------------------------------------------- controller

class Controller:
    """The minimum durable controller.

    Walks the source CSV in deterministic order, assesses each row, enrolls
    QUALIFIED candidates into the queue, and tracks provider write state.

    The controller is dry by default. Pass live=True to permit provider
    writes (which still go through providerwrites.perform and its gates).
    """

    def __init__(self, source_csv, *, live=False, notify_fn=None,
                 assess_fn=None, enroll_fn=None):
        self.source_csv = source_csv
        self.live = live
        self._notify = notify_fn or _no_notify
        self._assess = assess_fn
        self._enroll = enroll_fn

    def run(self, limit=None):
        """Walk the source from the checkpoint's position.

        Returns a summary dict with counts and the final checkpoint state.
        """
        cp = load_checkpoint()
        if cp["batch_id"] is None:
            cp["batch_id"] = "batch-%s" % uuid.uuid4().hex[:12]
            cp["batch_state"] = BATCH_RUNNING
            save_checkpoint(cp)
            self._notify("controller_batch_started",
                         {"batch_id": cp["batch_id"]})

        if cp["batch_state"] == BATCH_COMPLETE:
            return {"status": "already_complete", "checkpoint": cp}

        start_row = cp["source_position"] + 1
        counts = {
            "assessed": 0,
            "qualified": 0,
            "held": 0,
            "not_qualified": 0,
            "enrolled": 0,
            "skipped_duplicate": 0,
        }
        limit_reached = False
        total_rows = 0

        try:
            with io.open(self.source_csv, encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                for i, row in enumerate(reader, start=1):
                    total_rows = i
                    if i < start_row:
                        continue
                    if limit is not None and counts["assessed"] >= limit:
                        limit_reached = True
                        break

                    counts["assessed"] += 1
                    source_row = i

                    if str(source_row) in cp["enrolled"]:
                        counts["skipped_duplicate"] += 1
                        cp["source_position"] = source_row
                        save_checkpoint(cp)
                        continue

                    disposition, reason, detail = self._assess_row(row)
                    counts[_count_key(disposition)] += 1

                    if disposition == DISPOSITION_QUALIFIED:
                        record_id = self._enroll_row(row, source_row, detail)
                        if record_id:
                            cp["enrolled"][str(source_row)] = {
                                "record_id": record_id,
                                "disposition": disposition,
                                "reason": reason[:200],
                                "approval_hash": detail.get("approval_hash", ""),
                                "provider_campaign_id": detail.get(
                                    "provider_campaign_id", ""),
                                "write_state": WRITE_PENDING,
                            }
                            counts["enrolled"] += 1
                    else:
                        cp["enrolled"][str(source_row)] = {
                            "record_id": None,
                            "disposition": disposition,
                            "reason": reason[:200],
                        }

                    cp["source_position"] = source_row
                    save_checkpoint(cp)

        except KeyboardInterrupt:
            self._notify("controller_interrupted",
                         {"batch_id": cp["batch_id"],
                          "source_position": cp["source_position"]})
            raise
        except Exception as e:
            self._notify("controller_error",
                         {"batch_id": cp["batch_id"],
                          "source_position": cp["source_position"],
                          "error": "%s: %s" % (type(e).__name__, str(e)[:200])})
            raise

        if not limit_reached and cp["source_position"] >= total_rows:
            cp["batch_state"] = BATCH_COMPLETE
            save_checkpoint(cp)
            self._notify("controller_batch_complete",
                         {"batch_id": cp["batch_id"],
                          "source_position": cp["source_position"],
                          "enrolled": counts["enrolled"]})
            return {"status": "complete", "counts": counts, "checkpoint": cp}
        else:
            return {"status": "paused", "counts": counts, "checkpoint": cp}

    def _assess_row(self, row):
        """One row's disposition. Delegates to the injected assess_fn or the
        default canary walk assessment."""
        if self._assess is not None:
            return self._assess(row)
        from scripts import canary_candidate_walk as ccw
        recs = store.load()
        by_domain = {}
        for r in recs:
            d = (r.get("domain") or "").strip().lower()
            if d and d not in by_domain:
                by_domain[d] = r
        from . import clients
        config = clients.load("productive")
        return ccw.assess(row, by_domain, config)

    def _enroll_row(self, row, source_row, detail):
        """Enroll a QUALIFIED row into the queue. Returns the record id.

        Dry by default: records the enrollment in the checkpoint but does not
        mutate the queue or call any provider. With live=True, delegates to
        the injected enroll_fn.
        """
        if not self.live:
            return "dry-run-%s" % uuid.uuid4().hex[:8]
        if self._enroll is not None:
            return self._enroll(row, source_row, detail)
        return None


def _count_key(disposition):
    if disposition == DISPOSITION_QUALIFIED:
        return "qualified"
    if disposition == DISPOSITION_HELD:
        return "held"
    return "not_qualified"


def _no_notify(event_type, fields):
    pass


# --------------------------------------------------------------- duplicate

def is_duplicate(cp, source_row):
    """Whether this source row has already been processed."""
    return str(source_row) in cp.get("enrolled", {})


def enrolled_record_id(cp, source_row):
    """The record id for an enrolled source row, or None."""
    entry = cp.get("enrolled", {}).get(str(source_row))
    if entry:
        return entry.get("record_id")
    return None


def write_state(cp, source_row):
    """The provider write state for an enrolled source row, or None."""
    entry = cp.get("enrolled", {}).get(str(source_row))
    if entry:
        return entry.get("write_state")
    return None


def update_write_state(source_row, new_state):
    """Update the write state for one enrolled source row. Atomic."""
    if new_state not in WRITE_STATES:
        raise ValueError("unknown write state: %r" % new_state)
    cp = load_checkpoint()
    key = str(source_row)
    if key not in cp.get("enrolled", {}):
        raise KeyError("source row %d is not enrolled" % source_row)
    cp["enrolled"][key]["write_state"] = new_state
    save_checkpoint(cp)
    return cp


# --------------------------------------------------------------- CLI

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", default=os.path.join(
        "work", "Productive",
        "productive_ICP_safe_to_send (1).csv"),
        help="path to the source CSV")
    ap.add_argument("--limit", type=int, default=None,
                    help="how many rows to assess in this run")
    ap.add_argument("--live", action="store_true",
                    help="permit provider writes (default: dry run)")
    args = ap.parse_args()

    if not os.path.exists(args.source):
        print("source not found: %s" % args.source, file=sys.stderr)
        sys.exit(1)

    ctrl = Controller(args.source, live=args.live)
    result = ctrl.run(limit=args.limit)
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
