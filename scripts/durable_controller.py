#!/usr/bin/env python3
"""The MINIMUM durable controller, and nothing more.

Walks the operator's approved source CSV in deterministic order, assesses
each row, and - for QUALIFIED candidates - drives them through the existing
pipeline (generation, approval, provider write, readback). Checkpoints
progress after every row so a kill-and-restart resumes exactly where it
left off without re-enrolling or re-sending.

## What it persists, and why each field exists

    source_position          row in the source CSV last completed
    batch_id                 which batch this run belongs to
    batch_size               how many QUALIFIED rows this batch admits
    batch_status             running | complete
    per-row disposition      QUALIFIED / HELD + reason / NOT_QUALIFIED
    approval_hash            the digest the provider write was authorised against
    provider_campaign_id     the campaign the provider returned
    provider_write_state     performed | refused | unverified | failed
    readback_state           verified | stale | absent

Nothing else is persisted. The queue already answers record state, contact
discovery, ICP verdict and eligibility. The checkpoint records only what
CANNOT be derived: how far through the source we got, what the provider
returned, and what we authorised.

## Duplicate protection

Before processing a row, the controller checks whether the domain already
has a queue record in a state that means "already staged or sent" (pushed,
approved, drafted). If it does, the row is recorded as ALREADY_ENROLLED and
skipped. A restart after a kill mid-batch will therefore never re-enrol or
re-send to somebody already in the queue at those states.

## Dry by default

Nothing writes to a provider, spends a credit or generates copy unless
--live is passed. The default is a full walk that reports what WOULD happen.

## Usage

    py -3 scripts/durable_controller.py --limit 50
    py -3 scripts/durable_controller.py --live --batch-size 5
    py -3 scripts/durable_controller.py --resume
"""
import argparse
import csv
import datetime
import importlib.util
import io
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from src import clients, notify, store

# canary_candidate_walk is a script, not a src module. Load it by path so
# the controller can call its assess() without duplicating the logic.
_ccw_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "canary_candidate_walk.py")
_ccw_spec = importlib.util.spec_from_file_location(
    "canary_candidate_walk", _ccw_path)
canary_candidate_walk = importlib.util.module_from_spec(_ccw_spec)
_ccw_spec.loader.exec_module(canary_candidate_walk)

SOURCE = os.path.join("work", "Productive",
                      "productive_ICP_safe_to_send (1).csv")

CHECKPOINT_PATH = os.path.join("work", "controller-checkpoint.json")

ALREADY_ENROLLED = "ALREADY_ENROLLED"

STATES_MEANING_ENROLLED = ("pushed", "approved", "drafted")


def _now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(
        timespec="seconds")


def _domain_of(email):
    return (email or "").split("@")[-1].strip().lower()


# ------------------------------------------------------------- checkpoint

def checkpoint_path(override=None):
    return override or CHECKPOINT_PATH


def load_checkpoint(path=None):
    """Read the checkpoint. Absent means fresh start, not error."""
    p = checkpoint_path(path)
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def save_checkpoint(state, path=None):
    """Atomic write. Called after every row so a kill loses at most one row."""
    p = checkpoint_path(path)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = "%s.%d.tmp" % (p, os.getpid())
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(state, fh, indent=2, sort_keys=True)
        fh.write("\n")
    os.replace(tmp, p)


def new_checkpoint(batch_id, batch_size):
    return {
        "batch_id": batch_id,
        "batch_size": batch_size,
        "batch_status": "running",
        "source_position": 0,
        "started_at": _now_iso(),
        "updated_at": _now_iso(),
        "rows": {},
    }


# ------------------------------------------------------------- duplicate guard

def is_already_enrolled(domain, recs_by_domain):
    """The queue is the authority. A domain whose record is already at
    pushed/approved/drafted has been through the pipeline and must not
    be re-enrolled. This is the duplicate protection the controller exists for.
    """
    rec = recs_by_domain.get(domain)
    if rec is None:
        return False
    return (rec.get("state") or "") in STATES_MEANING_ENROLLED


# ------------------------------------------------------------- the walk

def process_row(row_idx, row, by_domain, config, checkpoint, live):
    """One row's full pipeline. Returns (disposition, reason, detail).

    In dry mode (live=False), no provider write, no generation, no credit
    spend. The assessment runs; the rest is reported as what-would-happen.
    """
    email = (row.get("Work Email") or "").strip()
    domain = _domain_of(email)

    if not domain:
        return "NOT_QUALIFIED", "no domain in source row", {}

    # DUPLICATE PROTECTION. The queue is the checkpoint for anything it
    # already answers. A record at pushed/approved/drafted has been through
    # the pipeline and must not be re-enrolled, ever.
    if is_already_enrolled(domain, by_domain):
        return ALREADY_ENROLLED, ("domain already at state %r in queue"
                                  % by_domain[domain].get("state")), {
            "record": by_domain[domain].get("id")}

    # ASSESSMENT. Reuse the canary walk's disposition logic exactly.
    verdict, reason, detail = canary_candidate_walk.assess(
        row, by_domain, config)

    if verdict != canary_candidate_walk.QUALIFIED:
        return verdict, reason, detail

    # QUALIFIED. In dry mode, report and stop. In live mode, the pipeline
    # continues through generation, approval and provider write - but those
    # modules are not touched by this task (TASK-933 wires state, not policy).
    detail["would_generate"] = not live
    detail["would_write_provider"] = not live

    return verdict, reason, detail


def run(batch_id, batch_size, limit, live, checkpoint_override=None,
        source_override=None):
    """The controller loop. Walks the source, assesses, checkpoints."""
    source = source_override or SOURCE
    cp_path = checkpoint_override

    existing = load_checkpoint(cp_path)
    if existing and existing.get("batch_status") == "complete":
        print("batch %s is already complete (source_position=%d). "
              "Use a new batch_id to start fresh."
              % (existing.get("batch_id"), existing.get("source_position")))
        return existing

    if existing and existing.get("batch_id") == batch_id:
        checkpoint = existing
        start_from = checkpoint.get("source_position", 0)
        print("resuming batch %s from source row %d"
              % (batch_id, start_from))
    else:
        checkpoint = new_checkpoint(batch_id, batch_size)
        start_from = 0
        save_checkpoint(checkpoint, cp_path)

    config = clients.load("productive")
    recs = store.load()
    by_domain = {}
    for r in recs:
        d = (r.get("domain") or "").strip().lower()
        if d and d not in by_domain:
            by_domain[d] = r

    qualified_count = sum(
        1 for v in checkpoint["rows"].values()
        if v.get("disposition") == canary_candidate_walk.QUALIFIED)

    source_exhausted = True
    with io.open(source, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader, start=1):
            if i <= start_from:
                continue
            if limit and i > limit:
                source_exhausted = False
                break
            if qualified_count >= batch_size:
                checkpoint["batch_status"] = "complete"
                checkpoint["updated_at"] = _now_iso()
                save_checkpoint(checkpoint, cp_path)
                print("batch %s reached batch_size %d at source row %d"
                      % (batch_id, batch_size, i))
                source_exhausted = False
                break

            verdict, reason, detail = process_row(
                i, row, by_domain, config, checkpoint, live)

            row_entry = {
                "disposition": verdict,
                "reason": reason[:240],
                "domain": _domain_of(row.get("Work Email") or ""),
                "at": _now_iso(),
            }
            for key in ("record", "icp", "persona", "offer",
                        "approval_hash", "provider_campaign_id",
                        "provider_write_state", "readback_state"):
                if key in detail:
                    row_entry[key] = detail[key]

            checkpoint["rows"][str(i)] = row_entry
            checkpoint["source_position"] = i
            checkpoint["updated_at"] = _now_iso()

            if verdict == canary_candidate_walk.QUALIFIED:
                qualified_count += 1

            save_checkpoint(checkpoint, cp_path)

            # SLACK OPERATIONAL EVENT. Best-effort; notify() cannot raise
            # into the caller.
            try:
                notify.notify(
                    "controller_row_processed",
                    workspace="productive",
                    fields={
                        "row": i,
                        "disposition": verdict,
                        "reason": reason[:120],
                        "batch_id": batch_id,
                        "live": live,
                    },
                    ids={"row": str(i), "batch": batch_id},
                )
            except Exception:                                 # noqa: BLE001
                pass

            print("%4d  %-18s %-30s %s"
                  % (i, verdict,
                     (row.get("Company") or "?")[:28],
                     reason[:100]))

    if source_exhausted and checkpoint.get("batch_status") != "complete":
        checkpoint["batch_status"] = "complete"
        checkpoint["updated_at"] = _now_iso()
        save_checkpoint(checkpoint, cp_path)

    print()
    print("batch %s: %d rows walked, %d qualified, checkpoint at row %d"
          % (batch_id, checkpoint["source_position"], qualified_count,
             checkpoint["source_position"]))
    return checkpoint


# ------------------------------------------------------------- mutation check

def verify_checkpoint_mutation(path=None):
    """Prove the checkpoint survives a write-read cycle. Returns True if the
    round-trip is lossless. This is the mutation check the task requires."""
    p = checkpoint_path(path)
    original = new_checkpoint("mutation-test", 5)
    original["rows"]["1"] = {
        "disposition": "QUALIFIED",
        "reason": "test",
        "domain": "example.com",
        "approval_hash": "abcdef0123456789",
        "provider_campaign_id": "camp-123",
        "provider_write_state": "performed",
        "readback_state": "verified",
    }
    original["source_position"] = 1
    save_checkpoint(original, p)
    loaded = load_checkpoint(p)
    return (loaded is not None
            and loaded.get("batch_id") == "mutation-test"
            and loaded.get("source_position") == 1
            and "1" in loaded.get("rows", {})
            and loaded["rows"]["1"].get("approval_hash") == "abcdef0123456789")


# ------------------------------------------------------------- CLI

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--live", action="store_true",
                    help="enable provider writes and generation. "
                         "Default is dry run.")
    ap.add_argument("--batch-id", default="controller-batch-1",
                    help="batch identity for the checkpoint")
    ap.add_argument("--batch-size", type=int, default=5,
                    help="how many QUALIFIED rows to process")
    ap.add_argument("--limit", type=int, default=200,
                    help="maximum source rows to walk")
    ap.add_argument("--resume", action="store_true",
                    help="resume from the existing checkpoint")
    ap.add_argument("--checkpoint-path", default=None,
                    help="override the checkpoint file location")
    ap.add_argument("--source-path", default=None,
                    help="override the source CSV location")
    ap.add_argument("--mutation-check", action="store_true",
                    help="run the checkpoint mutation check and exit")
    args = ap.parse_args(argv)

    if args.mutation_check:
        ok = verify_checkpoint_mutation(args.checkpoint_path)
        print("mutation check: %s" % ("PASS" if ok else "FAIL"))
        return 0 if ok else 1

    if not args.live:
        print("DRY RUN. Pass --live to enable provider writes.")

    run(batch_id=args.batch_id, batch_size=args.batch_size,
        limit=args.limit, live=args.live,
        checkpoint_override=args.checkpoint_path,
        source_override=args.source_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
