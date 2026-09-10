#!/usr/bin/env python3
"""The runner. BUILD-SPEC phase 8.

Walks a batch through the pipeline. It orchestrates the phases and owns none of
their logic: every decision still belongs to the module that made it.

  ingest -> enrich -> qualify -> personas -> generate -> render -> push

Resumable, because the queue is the state. Each record carries which stages it
has finished, so a crash at record 40 of 500 restarts at 40 and the first 39 are
not paid for twice. A stage that fails on one record fails that record only: the
other 499 carry on, and the failure is written onto the record that caused it.

Two separate explicit gates, neither of them on by default:

  --spend   enrich and generate may call providers and the model, and credits
            are spent. Without it they run as dry plans.
  --live    push for real. This build refuses it: phase 7 prepares only.

  python -m src.run --source batches/x.csv --client productive --lane domains
  python -m src.run --spend --cap 200
"""
import argparse

from . import (cadence, clients, enrich, events, generate, ingest, lint, llm, mx,
               personas, push, qualify, render, research, store)
from .providers import apify

# `qualify` sits between the company-level evidence and the person-level
# spend, which is what PLAYBOOK section 1 means by company first. It was
# missing: the runner went straight from `enrich` to `personas`, so no verdict
# was ever produced on the real execution path and `enrich` spent person
# credits on companies nobody had assessed. It is a fixed point rather than a
# single pass - enrichment gathers free company facts, qualification reads
# them, and the *next* pass is the one allowed to buy people.
STAGES = ("enrich", "qualify", "personas", "generate", "render", "push")
PER_RECORD = ("enrich", "qualify", "personas", "generate")

TERMINAL = ("dropped", "pushed")


class RunnerError(RuntimeError):
    """A stage could not run at all, as opposed to failing on one record."""


def stages_of(rec):
    return rec.setdefault("stages", {})


def is_done(rec, stage):
    return stages_of(rec).get(stage, {}).get("status") == "done"


def mark(rec, stage, status, note=""):
    stages_of(rec)[stage] = {"status": status, "at": store.now(), "note": note}
    if status == "failed":
        store.log(rec, stage, f"failed: {note}")
    return rec


def needs(rec, stage):
    """Whether this record still has work to do in this stage."""
    if rec.get("state") in TERMINAL:
        return False
    if is_done(rec, stage):
        return False
    return True


# ------------------------------------------------------------ the stages

def stage_enrich(recs, spend, cap, notes):
    budget = enrich.Budget(cap)
    # The client's own config, and the scrape ceiling that goes with it.
    #
    # This stage called `enrich_record` with neither. `enrich.run` threads
    # both; the batch runner - the path an operator actually uses to walk a
    # whole list - did not, so on this path the verification policy silently
    # fell back to module defaults instead of the client's, `research` never
    # ran at all because it is gated on `config`, and `max_runs_per_batch` was
    # unenforced because `research.run` only consults a budget it is handed.
    # Every other per-record stage already loads the config this way.
    scrape_budget = research.RunBudget(None)
    # One MX cache for the whole stage, saved once. `enrich_record` used to load
    # it per record and could never persist it, so every run re-resolved every
    # domain. See the comment there.
    mx_cache = mx.load_cache()
    mx_cache_at_start = len(mx_cache)
    touched, configs = 0, {}
    for rec in recs:
        if not needs(rec, "enrich"):
            continue
        client = rec.get("client")
        if client not in configs:
            try:
                configs[client] = clients.load(client)
            except clients.ConfigError as e:
                configs[client] = None
                notes.append(f"{client}: {e}")
        config = configs[client]
        if scrape_budget.cap is None and config:
            scrape_budget.cap = apify.settings(config)["max_runs_per_batch"]
        try:
            refusals_before = len(budget.refused)
            if spend:
                enrich.enrich_record(rec, budget, live=True, log=notes,
                                     config=config,
                                     scrape_budget=scrape_budget,
                                     mx_cache=mx_cache)
            else:
                planned = enrich.plan(rec, config)
                for op in planned:
                    budget.charge(op["cost"], f"{rec['id']}:{op['call']}")
                store.log(rec, "enrich",
                          f"dry run: {len(planned)} call(s) planned, "
                          f"{sum(o['cost'] for o in planned)} credits")
            # "done" is a promise the next run reads as "never look again".
            # A record the cap cut short has not finished, so it is marked
            # partial and `needs()` picks it up when there is budget for it.
            refused = len(budget.refused) > refusals_before
            # The same reasoning covers a record held back by the ICP gate:
            # it has not finished, it is waiting for a verdict, and saying
            # `done` would mean the pass that finally has one never looks.
            pending = spend and enrich.person_level_pending(rec)
            mark(rec, "enrich",
                 ("partial" if (refused or pending) else "done")
                 if spend else "planned")
            touched += 1
        except Exception as e:                       # one record, not the batch
            mark(rec, "enrich", "failed", f"{type(e).__name__}: {e}")
    if spend and len(mx_cache) != mx_cache_at_start:
        mx.save_cache(mx_cache)
    return {"records": touched, "spent": budget.spent,
            "refused": budget.refused,
            "mx_resolved": len(mx_cache) - mx_cache_at_start}


def stage_qualify(recs, notes):
    """The verdict, before anything spends a person credit on it.

    `qualify.company` spends nothing, and `qualify.needs_work` compares a
    fingerprint of the facts the last verdict was derived from - so this
    re-runs exactly the companies enrichment has just learned something about
    and skips the rest. That is also why a finished stage is not enough to
    skip on: the facts change underneath it, and a verdict from before they
    changed is not a verdict about this company any more.
    """
    touched, configs = 0, {}
    for rec in recs:
        if not needs(rec, "qualify") and not qualify.needs_work(rec):
            continue
        if rec.get("state") in TERMINAL:
            continue
        client = rec.get("client")
        if client not in configs:
            try:
                configs[client] = clients.load(client)
            except clients.ConfigError as e:
                configs[client] = None
                notes.append(f"{client}: {e}")
        if configs[client] is None:
            # The same answer `stage_personas` gives, and for the same reason:
            # a client with no config is not a failed record, it is a client
            # nobody has configured. It stays unqualified, which the spend
            # gate already reads as "no person credits".
            mark(rec, "qualify", "skipped", f"no config for client {client}")
            continue
        try:
            qualify.company(rec, configs[client])
            mark(rec, "qualify", "done")
            touched += 1
        except Exception as e:                   # one record, not the batch
            mark(rec, "qualify", "failed", f"{type(e).__name__}: {e}")
    return {"records": touched}


def unkeyed(rec):
    """Contacts that arrived after this stage last said it was finished.

    `identity.assign_keys` runs in `stage_personas`, and a contact without a
    key is invisible to everything that looks one up: `eligibility.for_record`
    reads `timeline.get(contact["key"])` and returns *no decisions at all* for
    the record - silence that reads exactly like "nothing is wrong".

    That is reachable because a stage marks itself `done` against the record
    it saw. Personas ran on the first pass, when the account had no people;
    person discovery then found sixteen, and `needs()` has said no ever since.
    The same shape as a cap-shortened enrichment claiming it finished: the
    stage is done with what it was given, and what it was given has changed.
    """
    return [c for c in (rec.get("contacts") or []) if not c.get("key")]


def stage_personas(recs, notes):
    touched, configs = 0, {}
    for rec in recs:
        if not needs(rec, "personas") and not unkeyed(rec):
            continue
        client = rec.get("client")
        if client not in configs:
            try:
                configs[client] = clients.load(client)
            except clients.ConfigError as e:
                configs[client] = None
                notes.append(f"{client}: {e}")
        if configs[client] is None:
            mark(rec, "personas", "skipped", f"no config for client {client}")
            continue
        try:
            personas.select(rec, configs[client])
            personas.export(rec)
            mark(rec, "personas", "done")
            touched += 1
        except Exception as e:
            mark(rec, "personas", "failed", f"{type(e).__name__}: {e}")
    return {"records": touched}


def stage_generate(recs, model, spend, notes):
    touched = 0
    for rec in recs:
        if not needs(rec, "generate"):
            continue
        if not spend or model is None:
            planned = generate.plan(rec)
            mark(rec, "generate", "planned", f"{len(planned)} model call(s) needed")
            continue
        try:
            client = clients.load(rec.get("client"))
        except clients.ConfigError:
            client = None
        try:
            generate.generate_record(rec, model, client)
            outstanding = generate.plan(rec)
            mark(rec, "generate", "done" if not outstanding else "partial",
                 f"{len(outstanding)} step(s) still outstanding")
            touched += 1
        except Exception as e:
            mark(rec, "generate", "failed", f"{type(e).__name__}: {e}")
    return {"records": touched}


def stage_render(recs, notes):
    """Batch level: the review sheet, the push file and the summary."""
    try:
        summary = render.build()
        return {"emails": summary["emails"], "clean": summary["clean"],
                "held": summary["held"], "failed": summary["failed"]}
    except Exception as e:
        notes.append(f"render failed: {type(e).__name__}: {e}")
        return {"error": str(e)}


def stage_push(recs, day, live, notes):
    """Preparation only. `live` is refused by push.py, deliberately."""
    if live:
        raise push.LiveSendNotEnabled(
            "the runner will not send. Phase 7 prepares payloads only.")
    try:
        result = push.run(day=day)
        with store.transaction() as recs:
            push.record_prepared(recs, result["ready"])
        return {"email": result["counts"]["email"],
                "linkedin": result["counts"]["linkedin"],
                "skipped": result["counts"]["skipped"]}
    except Exception as e:
        notes.append(f"push preparation failed: {type(e).__name__}: {e}")
        return {"error": str(e)}


# ------------------------------------------------------------- the runner

def run(source=None, client=None, lane=None, model=None, day=21, spend=False,
        live=False, cap=None, limit=None, stages=STAGES, ids=None):
    """Walk the batch. Dry by default: no credits, no model, nothing sent.

    `cap=None` means unlimited, deliberately, for a caller writing it in code.
    The refusal lives in `main()` - see `enrich.require_cap`.
    """
    if live:
        raise push.LiveSendNotEnabled(
            "live is not available in this build: phase 7 prepares payloads only.")

    notes, report = [], {}

    if source:
        ingested = ingest.run(source, client=client, lane=lane)
        report["ingest"] = {"queued": len(ingested["queued"]),
                            "dropped": len(ingested["dropped"]),
                            "skipped": len(ingested["skipped"])}

    recs = store.load()
    targets = [r for r in recs if ids is None or r["id"] in ids]
    if limit:
        targets = targets[:limit]

    if "enrich" in stages:
        report["enrich"] = stage_enrich(targets, spend, cap, notes)
    if "qualify" in stages:
        report["qualify"] = stage_qualify(targets, notes)
    if "personas" in stages:
        report["personas"] = stage_personas(targets, notes)
    if "generate" in stages:
        report["generate"] = stage_generate(targets, model, spend, notes)

    store.save(recs)                      # one write, after the per-record stages

    if "render" in stages:
        report["render"] = stage_render(targets, notes)
    if "push" in stages:
        report["push"] = stage_push(targets, day, live, notes)

    report["states"] = store.stats(store.load())["states"]
    report["failures"] = [
        {"id": r["id"], "stage": name, "why": info.get("note")}
        for r in store.load() for name, info in (r.get("stages") or {}).items()
        if info.get("status") == "failed"]
    report["notes"] = notes
    report["spend"] = spend
    return report


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m src.run")
    p.add_argument("--source", help="a batch file or folder to ingest first")
    p.add_argument("--client")
    p.add_argument("--lane", choices=list(store.LANES))
    p.add_argument("--day", type=int, default=21)
    p.add_argument("--cap", type=int, help="credit ceiling for this run")
    p.add_argument("--limit", type=int)
    p.add_argument("--id", action="append", dest="ids")
    p.add_argument("--stage", action="append", dest="stages", choices=list(STAGES))
    p.add_argument("--spend", action="store_true",
                   help="allow provider and model calls, and spend credits")
    p.add_argument("--live", action="store_true",
                   help="explicit gate; this build refuses and explains why")
    a = p.parse_args(argv)

    if a.live:
        print("REFUSED: this build cannot send. Phase 7 prepares payloads only.")
        return 2

    # `--spend` with no `--cap` was an unbounded spend over a whole batch. See
    # `enrich.require_cap` for the number that makes this matter.
    try:
        enrich.require_cap(a.spend, a.cap)
    except enrich.NoBudget as e:
        print(f"REFUSED: {e}")
        return 2

    report = run(source=a.source, client=a.client, lane=a.lane, day=a.day,
                 spend=a.spend, cap=a.cap, limit=a.limit,
                 stages=tuple(a.stages) if a.stages else STAGES, ids=a.ids)

    print("DRY RUN" if not a.spend else "LIVE ENRICHMENT (credits spent)")
    for stage in ("ingest", "enrich", "personas", "generate", "render", "push"):
        if stage in report:
            detail = ", ".join(f"{k}={v}" for k, v in report[stage].items())
            print(f"  {stage:<10} {detail}")
    print(f"  states     {report['states']}")
    for failure in report["failures"]:
        print(f"  FAILED     {failure['id']} in {failure['stage']}: {failure['why']}")
    for note in report["notes"]:
        print(f"  note       {note}")
    if not a.spend:
        print("\nadd --spend to call providers and the model. --live is refused.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
