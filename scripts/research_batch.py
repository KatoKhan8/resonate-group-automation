#!/usr/bin/env python3
"""Deterministic, resumable batch controller for the evidence backlog.

Operator decision, Zvonimir, 2026-09-30: the evidence bar stays. A shortfall
is a research problem, per company: insufficient evidence -> run the canonical
Apify/research path -> richer sourced pack -> re-evaluate -> still insufficient
-> HELD with the exact reason -> continue.

This script walks the operator's approved source order and runs the canonical
enrichment path for each account that `research.why(rec, for_copy=True)`
reports as `NEED_COPY_EVIDENCE`. It does NOT rebuild the path - it goes
through `enrich.enrich_record`, which is the only call site that owns the
`spend` ledger.

Order, cap, resume, disposition:

  ORDER is the CSV's, not queue order and not cheapest-first.
  `scripts/canary_candidate_walk.py` is the precedent.

  CAP is per run and REFUSED rather than exceeded. An uncapped live run is
  refused, not given a default. `enrich.require_cap` is the precedent.

  RESUME is free: an account that now has enough admitted rows is simply no
  longer in the NEED_COPY_EVIDENCE set, so re-running the command IS the
  resume. No second state file.

  DISPOSITION is per account: QUALIFIED (enough admitted rows after research),
  HELD (still insufficient, with the exact reason and admitted-row count),
  NOT_QUALIFIED (rejected, no contact, no record). Reported separately so an
  easy account never quietly stands in for an attempted one.

DRY RUN IS THE DEFAULT. Nothing is called and nothing is written. A live run
needs --live AND --cap.

    py -3 scripts/research_batch.py --limit 20
    py -3 scripts/research_batch.py --live --cap 5 --limit 20
"""
import argparse
import csv
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import clients, enrich, evidence as ev, research, store

SOURCE = os.path.join("work", "Productive",
                      "productive_ICP_safe_to_send (1).csv")

QUALIFIED = "QUALIFIED"
HELD = "HELD"
NOT_QUALIFIED = "NOT_QUALIFIED"
SKIPPED = "SKIPPED"


def _domain_of(email):
    return (email or "").split("@")[-1].strip().lower()


def _admitted_count(rec):
    """How many ADMISSIBLE evidence rows this record has.

    Through `evidence.select`, the same filter the prompt is built through.
    A row scored WEAK is on the record and reaches nobody.
    """
    rows = list(rec.get("research") or [])
    if not rows:
        return 0
    try:
        admitted = list(ev.select(rows, limit=len(rows)))
    except Exception:
        return 0
    return len(admitted)


def _classify(rec, config):
    """The disposition for an account that does NOT need copy evidence.

    Called AFTER research to re-evaluate. Returns (disposition, reason).
    """
    need = research.why(rec, for_copy=True)
    if need is None:
        return QUALIFIED, ("sufficient admissible evidence: %d row(s)"
                           % _admitted_count(rec))
    if need == research.NEED_COPY_EVIDENCE:
        return HELD, ("insufficient admissible evidence for prospect-facing "
                      "copy: %d admitted row(s), needs %d"
                      % (_admitted_count(rec), research.MIN_COPY_EVIDENCE_ROWS))
    return HELD, "research needed: %s" % need


def _not_qualified_reason(rec, domain):
    """Why this account is NOT_QUALIFIED, or None if it is not."""
    if rec is None:
        return ("no canonical record for %s: the company has not been "
                "through intake" % domain)
    state = rec.get("state")
    if state in ("dropped", "do_not_contact"):
        return "record state is %r" % state
    if (rec.get("qualification") or {}).get("verdict", {}).get(
            "icp_status") == "rejected":
        return "ICP rejected"
    if not any(c.get("email") or c.get("linkedin")
               for c in rec.get("contacts") or ()):
        return "no contact to write to"
    return None


def run_batch(live=False, cap=None, limit=None, source=None):
    """Walk the source order and research accounts that need it.

    Returns a result dict with per-account dispositions and spend totals.

    `cap` bounds the number of accounts ATTEMPTED (researched), not the number
    walked. An account that is SKIPPED (already qualified, not qualified) does
    not count against the cap. A cap of zero is refused for a live run.

    `limit` bounds the number of CSV rows walked, for dry-run scoping.
    """
    source = source or SOURCE
    if live and cap is None:
        raise enrich.NoBudget(
            "a live run needs an explicit --cap. Pass --cap 0 to plan "
            "without spending.")
    if live and cap == 0:
        raise enrich.NoBudget(
            "--cap 0 on a live research batch would start Apify actors that "
            "bill in compute units the credit cap cannot see. Use dry run to "
            "plan, or pass a positive cap.")

    recs = store.load()
    by_domain = {}
    for r in recs:
        d = (r.get("domain") or "").strip().lower()
        if d and d not in by_domain:
            by_domain[d] = r

    budget = enrich.Budget(cap)
    scrape_budget = research.RunBudget(cap)
    research.crawl_cache_clear()

    counts = {QUALIFIED: 0, HELD: 0, NOT_QUALIFIED: 0, SKIPPED: 0}
    attempted = 0
    dispositions = []

    if not os.path.exists(source):
        return {"error": "source file not found: %s" % source,
                "dispositions": [], "counts": counts,
                "attempted": 0, "spent": 0}

    configs = {}
    with io.open(source, encoding="utf-8-sig", newline="") as f:
        for i, row in enumerate(csv.DictReader(f), start=1):
            if limit is not None and i > limit:
                break
            email = (row.get("Work Email") or "").strip()
            domain = _domain_of(email)
            company = (row.get("Company") or "").strip() or domain
            if not email or not domain:
                continue

            rec = by_domain.get(domain)
            skip_reason = _not_qualified_reason(rec, domain)
            if skip_reason:
                counts[NOT_QUALIFIED] += 1
                dispositions.append({
                    "row": i, "company": company, "domain": domain,
                    "disposition": NOT_QUALIFIED, "reason": skip_reason,
                    "record": rec["id"] if rec else None,
                    "admitted_before": None, "admitted_after": None,
                })
                continue

            need = research.why(rec, for_copy=True)
            if need is None:
                counts[QUALIFIED] += 1
                dispositions.append({
                    "row": i, "company": company, "domain": domain,
                    "disposition": QUALIFIED,
                    "reason": "already has sufficient evidence (%d admitted)"
                              % _admitted_count(rec),
                    "record": rec["id"],
                    "admitted_before": _admitted_count(rec),
                    "admitted_after": _admitted_count(rec),
                })
                continue

            if need != research.NEED_COPY_EVIDENCE:
                counts[SKIPPED] += 1
                dispositions.append({
                    "row": i, "company": company, "domain": domain,
                    "disposition": SKIPPED,
                    "reason": "need is %s, not copy evidence" % need,
                    "record": rec["id"],
                    "admitted_before": _admitted_count(rec),
                    "admitted_after": None,
                })
                continue

            # THIS ACCOUNT NEEDS RESEARCH. Check the cap.
            if cap is not None and attempted >= cap:
                counts[SKIPPED] += 1
                dispositions.append({
                    "row": i, "company": company, "domain": domain,
                    "disposition": SKIPPED,
                    "reason": "cap reached (%d attempted)" % attempted,
                    "record": rec["id"],
                    "admitted_before": _admitted_count(rec),
                    "admitted_after": None,
                })
                continue

            client_name = rec.get("client") or "productive"
            if client_name not in configs:
                try:
                    configs[client_name] = clients.load(client_name)
                except clients.ConfigError:
                    configs[client_name] = {}
            config = configs[client_name]

            admitted_before = _admitted_count(rec)

            if live:
                try:
                    enrich.enrich_record(
                        rec, budget, live=True, log=[],
                        config=config, scrape_budget=scrape_budget,
                        for_copy=True)
                except Exception as exc:
                    why = "%s: %s" % (type(exc).__name__, str(exc)[:160])
                    store.log(rec, "research_batch",
                              "enrichment failed: %s" % why)
                    counts[HELD] += 1
                    dispositions.append({
                        "row": i, "company": company, "domain": domain,
                        "disposition": HELD,
                        "reason": "enrichment failed: %s" % why,
                        "record": rec["id"],
                        "admitted_before": admitted_before,
                        "admitted_after": _admitted_count(rec),
                    })
                    attempted += 1
                    continue
                attempted += 1
            else:
                # DRY RUN: plan only, no provider calls, no attempt counted.
                enrich.enrich_record(
                    rec, budget, live=False, log=[],
                    config=config, scrape_budget=scrape_budget,
                    for_copy=True)

            # RE-EVALUATE after research.
            disposition, reason = _classify(rec, config)
            if disposition == QUALIFIED:
                counts[QUALIFIED] += 1
            else:
                counts[HELD] += 1
            dispositions.append({
                "row": i, "company": company, "domain": domain,
                "disposition": disposition, "reason": reason,
                "record": rec["id"],
                "admitted_before": admitted_before,
                "admitted_after": _admitted_count(rec),
            })

    if live:
        store.save(recs)
        research.flush_crawl_cache()

    return {
        "live": live,
        "cap": cap,
        "attempted": attempted,
        "counts": counts,
        "dispositions": dispositions,
        "spent": budget.spent,
        "refused": budget.refused,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--live", action="store_true",
                    help="actually call providers and spend credits")
    ap.add_argument("--cap", type=int, default=None,
                    help="max accounts to attempt (refused, not exceeded)")
    ap.add_argument("--limit", type=int, default=None,
                    help="max CSV rows to walk")
    ap.add_argument("--source", default=None,
                    help="override the source CSV path")
    args = ap.parse_args(argv)

    try:
        result = run_batch(live=args.live, cap=args.cap, limit=args.limit,
                           source=args.source)
    except enrich.NoBudget as e:
        print("REFUSED: %s" % e)
        return 2

    if result.get("error"):
        print("ERROR: %s" % result["error"])
        return 1

    head = "LIVE" if args.live else "DRY RUN"
    print("%s: walked %d row(s), attempted %d account(s)"
          % (head, len(result["dispositions"]), result["attempted"]))
    print()

    c = result["counts"]
    print("  qualified   : %d" % c[QUALIFIED])
    print("  held        : %d" % c[HELD])
    print("  not qualified: %d" % c[NOT_QUALIFIED])
    print("  skipped     : %d" % c[SKIPPED])
    print()

    for d in result["dispositions"]:
        print("  %4d  %-14s %-30s %s"
              % (d["row"], d["disposition"],
                 d["company"][:28], d["reason"][:100]))

    if result["refused"]:
        print()
        print("refused by cap:")
        for what in result["refused"]:
            print("  %s" % what)

    if not args.live:
        print()
        print("add --live --cap N to run it. --cap N bounds the attempts.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
