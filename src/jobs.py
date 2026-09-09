#!/usr/bin/env python3
"""Long work, made resumable and watchable.

## The problem this solves

A 5,000-domain upload cannot depend on one HTTP request staying open. It also
cannot depend on one *process* staying up: the operator will close the laptop,
the machine will sleep, and a provider will time out somewhere around company
3,000. WEB-READINESS already names this - "Long operations are synchronous...
A web layer needs a job runner; the work is already resumable, so a job can be
killed and restarted safely."

This is the job runner. What it adds is not concurrency - it adds a *record* of
work in progress that survives the process, so a restart continues rather than
starting over.

## What it deliberately is not

**It is not a thread pool pretending to be a queue.** The brief is explicit:
"Do not implement fake background concurrency if no worker exists." A job here
runs in whichever process called `run_step`, in bounded slices, checkpointing
after each. That is honest: it is a cursor over a batch, and one machine turns
the handle. `WORKER-MIGRATION` in the docs describes what changes when a real
queue arrives, and the answer is one function.

## Checkpointing

Every job carries a `cursor` - the id of the last record it finished - and a
`processed` count. A slice reads the batch, skips everything up to the cursor,
does at most `slice_size` records, and writes the cursor back. So:

- a crash loses at most one slice, never the batch
- one bad record is recorded in `failures` and the slice continues
- a resumed job re-reads state from the queue, which is where the real work
  landed, so the cursor is a hint rather than a second source of truth

That last point matters. If the cursor and the queue ever disagree, the queue
wins: the cursor exists to avoid re-doing work, not to decide whether work was
done.

## Safety

No job type here spends money by default. The ones that could - enrichment,
verification, research - carry `spends: True` and refuse unless the caller
passes an explicit budget, exactly as the CLI does. `run_step` never enables
live sending: there is no job type that sends.
"""
import argparse
import json
import os
import uuid

from . import store

# ------------------------------------------------------------------- types
#
# One per stage a batch moves through. The names match the pipeline in
# PLAYBOOK section 1 so an operator reading a job list is reading the same
# vocabulary as the docs.

INGEST = "ingest"
ICP_CLASSIFY = "icp_classify"
SEGMENT = "segment"
PLAN_DM = "plan_dm"
ENRICH = "enrich"
VERIFY = "verify"
RESEARCH = "research"
PERSONALIZE = "personalize"
RENDER = "render"
QA = "qa"
PREPARE_CAMPAIGN = "prepare_campaign"

TYPES = (INGEST, ICP_CLASSIFY, SEGMENT, PLAN_DM, ENRICH, VERIFY, RESEARCH,
         PERSONALIZE, RENDER, QA, PREPARE_CAMPAIGN)

# Which stages can cost money. A job of one of these types refuses to run
# without an explicit budget, which is the same rule the CLI applies and the
# reason `--live` exists there.
SPENDING_TYPES = (ENRICH, VERIFY, RESEARCH, PERSONALIZE)

# ---------------------------------------------------------------- statuses

QUEUED = "queued"
RUNNING = "running"
COMPLETED = "completed"
COMPLETED_WITH_HOLDS = "completed_with_holds"
FAILED = "failed"
CANCELLED = "cancelled"

STATUSES = (QUEUED, RUNNING, COMPLETED, COMPLETED_WITH_HOLDS, FAILED, CANCELLED)
TERMINAL = (COMPLETED, COMPLETED_WITH_HOLDS, FAILED, CANCELLED)

# How many records one slice touches. Small enough that a crash loses little,
# large enough that the bookkeeping is not the cost.
SLICE = 100

# The most failures a job tolerates before it stops and asks for a human. One
# bad record must not kill a batch; five hundred bad records is not a batch
# with a problem in it, it is a problem with the batch.
MAX_FAILURE_RATE = 0.25
MIN_FAILURES_BEFORE_ABORT = 20


class JobError(RuntimeError):
    """The job could not run. Nothing was changed."""


def path():
    """Beside the queue, so a job list and its work move together."""
    return os.path.abspath(os.environ.get("JOBS")
                           or os.path.join(os.path.dirname(store.queue_path()),
                                           "jobs.jsonl"))


def load():
    return store.read_jsonl(path())


def save(rows, timeout=None):
    with store.lock(timeout, for_path=path()):
        store.write_jsonl(path(), rows)


def transaction(timeout=None):
    return store.file_transaction(path(), timeout)


def new(job_type, client, batch=None, total=0, created_by="system",
        estimated_cost=None, note=""):
    """A job record. Created queued; nothing runs until `run_step`."""
    if job_type not in TYPES:
        raise JobError(f"unknown job type: {job_type}")
    return {
        "id": f"job-{uuid.uuid4().hex[:12]}",
        "type": job_type,
        "client": client,
        "batch": batch,
        "status": QUEUED,
        "created_at": store.now(),
        "created_by": created_by,
        "started_at": None,
        "finished_at": None,
        "total": int(total or 0),
        "processed": 0,
        "failed": 0,
        "held": 0,
        "progress": 0.0,
        # The resume point. See the module docstring: a hint, never a second
        # source of truth about whether work happened.
        "cursor": None,
        "slices": 0,
        "failures": [],
        "error": None,
        "spends": job_type in SPENDING_TYPES,
        "estimated_cost": estimated_cost,
        # Units consumed so far, against the budget the caller supplies on
        # every `run_step`. Stored on the job rather than held in a local, so
        # a resumed run cannot start its allowance over.
        "spent": 0,
        "budget": None,
        # Absent rather than zero: no provider in this stack reports per-call
        # spend, so a number here would be invented.
        "actual_cost": None,
        "note": note,
        "log": [],
    }


def append(job):
    with transaction() as rows:
        rows.append(job)
    return job


def get(job_id, rows=None):
    for row in rows if rows is not None else load():
        if row.get("id") == job_id:
            return row
    return None


def for_client(client, rows=None):
    rows = load() if rows is None else rows
    return [r for r in rows if client is None or r.get("client") == client]


def active(rows=None):
    return [r for r in (load() if rows is None else rows)
            if r.get("status") in (QUEUED, RUNNING)]


def _note(job, message):
    job.setdefault("log", []).append({"at": store.now(), "note": message})
    return job


def _announce_failure(job):
    """Tell the operations channel a job stopped. Never the client's.

    An aborted job names batches, providers and failure counts, which is the
    machine rather than the outcome. It also cannot be allowed to change what
    happened to the job: `notify.notify` swallows its own errors, and this
    function returns nothing so a caller cannot start depending on it.
    """
    from . import notify

    notify.notify(
        notify.FAILED_JOB,
        notify.workspace_for_client(job.get("client")),
        fields={"job_type": job.get("type"), "batch": job.get("batch"),
                "processed": job.get("processed") or 0,
                "failed": job.get("failed") or 0,
                "error": job.get("error"),
                "action": "the batch is the problem, not one record"},
        ids={"job_id": job.get("id")})


def _progress(job):
    total = job.get("total") or 0
    if not total:
        return 0.0
    return round(min(1.0, (job.get("processed") or 0) / float(total)), 4)


def should_abort(job):
    """Has this job failed enough times to be a problem with the batch?

    Both conditions, not either: a batch of ten where four fail is noise, and a
    batch of five thousand where twenty fail is a Tuesday.
    """
    failed = job.get("failed") or 0
    processed = job.get("processed") or 0
    if failed < MIN_FAILURES_BEFORE_ABORT:
        return False
    return processed and (failed / float(processed)) > MAX_FAILURE_RATE


def run_step(job, items, work, slice_size=SLICE, budget=None):
    """Advance one job by one slice. Returns the job.

    `items` is the full ordered list of things to process - records, usually.
    `work(item)` does one unit and returns one of "ok", "held" or raises.

    The whole point is that this is safe to call again: it skips to the cursor
    first, so calling it twice with the same job does not redo the slice.
    """
    if job.get("status") in TERMINAL:
        return job
    if job.get("spends") and budget is None:
        raise JobError(
            f"{job['type']} can spend credits and no budget was supplied; "
            "refusing to run rather than spending an unbounded amount. The "
            "budget is a count of RECORDS this job may touch, not of credits "
            "- one record can cost ten, so bound the credits with "
            "`enrich.Budget` as well")
    if job.get("spends"):
        job["budget"] = int(budget)

    if job.get("status") == QUEUED:
        job["status"] = RUNNING
        job["started_at"] = store.now()
        _note(job, "started")

    # Skip to the cursor. Done by identity rather than by index so that a batch
    # that grew between slices does not silently shift the resume point.
    ids = [_identity(i) for i in items]
    start = 0
    if job.get("cursor") is not None and job["cursor"] in ids:
        start = ids.index(job["cursor"]) + 1

    done = 0
    for item in items[start:]:
        if done >= slice_size:
            break
        if job.get("spends") and (job.get("spent") or 0) >= int(budget):
            # The cap is enforced here, not only asked for at the door. A
            # budget that is required but never counted against is a comfort
            # rather than a control, and CLAUDE.md is explicit that costs are
            # real and the cap comes before the fan-out. The job stays
            # RUNNING: raise the budget and call again, and it continues from
            # the cursor rather than starting over.
            _note(job, f"stopped at the budget of {int(budget)} record(s)")
            break
        try:
            outcome = work(item)
        except Exception as e:                    # one bad record, not a batch
            job["failed"] = (job.get("failed") or 0) + 1
            job.setdefault("failures", []).append({
                "id": _identity(item),
                "error": f"{type(e).__name__}: {str(e)[:160]}",
                "at": store.now(),
            })
            outcome = "failed"
        else:
            # A unit is counted when the work ran, not when it was attempted:
            # a record that raised before a provider was called cost nothing.
            #
            # A unit is one RECORD, not one credit. The two are not the same
            # number and the difference is not small: `decision-makers` costs
            # ten, so a budget of twenty records authorises up to two hundred
            # credits. The credit ceiling is `enrich.Budget`, which is
            # per-run and counts what each call actually costs. This counter
            # bounds how much work a job does; it does not bound what that
            # work spends, and the two need setting together.
            if job.get("spends"):
                job["spent"] = (job.get("spent") or 0) + 1
        if outcome == "held":
            job["held"] = (job.get("held") or 0) + 1
        job["processed"] = (job.get("processed") or 0) + 1
        job["cursor"] = _identity(item)
        done += 1
        if should_abort(job):
            job["status"] = FAILED
            job["finished_at"] = store.now()
            job["error"] = (f"stopped after {job['failed']} failures in "
                            f"{job['processed']} records: this is a problem "
                            "with the batch, not with one record")
            _note(job, "aborted on failure rate")
            job["progress"] = _progress(job)
            _announce_failure(job)
            return job

    job["slices"] = (job.get("slices") or 0) + 1
    job["progress"] = _progress(job)

    if start + done >= len(items):
        job["status"] = COMPLETED_WITH_HOLDS if job.get("held") else COMPLETED
        job["finished_at"] = store.now()
        _note(job, f"finished: {job['processed']} processed, "
                   f"{job.get('held') or 0} held, {job.get('failed') or 0} failed")
    return job


def run_to_completion(job, items, work, slice_size=SLICE, budget=None,
                      max_slices=10000):
    """Every slice, in this process. What the CLI and the tests use.

    A web request never calls this - it calls `run_step` and returns, so the
    browser gets a progress number rather than a timeout.
    """
    for _ in range(max_slices):
        run_step(job, items, work, slice_size=slice_size, budget=budget)
        if job.get("status") in TERMINAL:
            break
    return job


def cancel(job, why="cancelled by an operator"):
    if job.get("status") in TERMINAL:
        return job
    job["status"] = CANCELLED
    job["finished_at"] = store.now()
    job["error"] = why
    _note(job, why)
    return job


def _identity(item):
    if isinstance(item, dict):
        return item.get("id") or item.get("record_id") or item.get("key")
    return str(item)


def summarise(rows=None):
    """Counts by status and by type, for the operator's diagnostics page."""
    rows = load() if rows is None else rows
    by_status, by_type = {}, {}
    for row in rows:
        by_status[row.get("status")] = by_status.get(row.get("status"), 0) + 1
        by_type[row.get("type")] = by_type.get(row.get("type"), 0) + 1
    return {
        "jobs": len(rows),
        "by_status": dict(sorted(by_status.items())),
        "by_type": dict(sorted(by_type.items())),
        "active": len(active(rows)),
        "failed": by_status.get(FAILED, 0),
        "with_holds": by_status.get(COMPLETED_WITH_HOLDS, 0),
    }


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m src.jobs", description=__doc__)
    p.add_argument("--client")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    rows = for_client(args.client) if args.client else load()
    if args.json:
        print(json.dumps({"jobs": rows, "summary": summarise(rows)}, indent=2))
        return 0
    if not rows:
        print("no jobs")
        return 0
    for row in rows:
        print(f"  {row['id']}  {row['type']:<18} {row['status']:<22} "
              f"{row['processed']}/{row['total']}  "
              f"held {row.get('held') or 0}  failed {row.get('failed') or 0}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
