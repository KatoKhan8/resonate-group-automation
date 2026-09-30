#!/usr/bin/env python3
"""Batch the evidence backlog through the EXISTING canonical path.

Operator decision, Zvonimir, 2026-09-30: the evidence bar stays. A shortfall
is a research problem: insufficient evidence -> run the canonical Apify/research
path -> richer sourced pack -> re-evaluate -> still insufficient -> HELD with
the exact reason -> continue.

The path is already proved. `enrich_record` is the only call site that owns
the `spend` ledger and the batch goes through it with `for_copy=True`.

Order is the operator's approved source, not queue order. The cap is per-run
and refused rather than exceeded. Resumable from the estate: an account that
now has enough admitted rows is no longer in the need-set, so re-running IS
the resume.

    py -3 scripts/research_copy_batch.py --cap 5
    py -3 scripts/research_copy_batch.py --live --cap 1
"""
import argparse
import csv
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import clients, enrich, evidence as ev, mx, research, store

SOURCE = os.path.join("work", "Productive",
                      "productive_ICP_safe_to_send (1).csv")

QUALIFIED = "QUALIFIED"
HELD = "HELD"
NOT_QUALIFIED = "NOT_QUALIFIED"
NOT_ATTEMPTED = "NOT_ATTEMPTED"


def _domain_of(email):
    return (email or "").split("@")[-1].strip().lower()


def _eligible_for_research(rec):
    """Whether this record may be researched.

    Mirrors `_copy_evidence_missing` / `_heading_for_copy`: a rejected account
    is a decision not a gap, and an account with no contact has nobody to
    write to. Both are refused by the canonical path; the batch refuses them
    before it reaches the spend ledger.
    """
    if rec.get("state") in ("dropped", "do_not_contact"):
        return False
    if (rec.get("qualification") or {}).get("verdict", {}).get(
            "icp_status") == "rejected":
        return False
    if not any(c.get("email") or c.get("linkedin")
               for c in rec.get("contacts") or ()):
        return False
    return True


def _admitted_count(rec):
    """How many evidence rows `evidence.select` admits for this record."""
    rows = list(rec.get("research") or [])
    if not rows:
        return 0
    try:
        return len(list(ev.select(rows, limit=len(rows))))
    except Exception:
        return 0


def _copy_sufficient(rec):
    """Does this record already have enough admissible evidence for copy?"""
    if not _eligible_for_research(rec):
        return False
    return research.why(rec, for_copy=True) is None


class AccountCap:
    """A hard stop on how many accounts one batch may attempt.

    Refuses rather than exceeds. An uncapped default is not acceptable: the
    operator's omission is where unbounded spend comes from, and this is the
    same shape `enrich.require_cap` guards against at the credit level.
    """

    def __init__(self, cap):
        if cap is None:
            raise ValueError(
                "a cap is required. Pass --cap N to bound the run. "
                "An uncapped batch over 614 accounts is the exact failure "
                "`require_cap` was written to prevent.")
        self.cap = cap
        self.started = []
        self.refused = []

    def allow(self, account_id):
        if len(self.started) >= self.cap:
            self.refused.append(account_id)
            return False
        self.started.append(account_id)
        return True


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--live", action="store_true",
                    help="actually call providers. Dry run by default.")
    ap.add_argument("--cap", type=int, required=True,
                    help="max accounts to attempt research for (refused, "
                         "not exceeded)")
    ap.add_argument("--limit", type=int, default=None,
                    help="max source rows to walk (default: all)")
    args = ap.parse_args(argv)

    config = clients.load("productive")
    recs = store.load()

    by_domain = {}
    for r in recs:
        d = (r.get("domain") or "").strip().lower()
        if d and d not in by_domain:
            by_domain[d] = r

    budget = enrich.Budget(cap=None)
    account_cap = AccountCap(args.cap)
    scrape_budget = research.RunBudget(None)
    research.crawl_cache_clear()
    mx_cache = mx.load_cache()

    dispositions = []
    counts = {QUALIFIED: 0, HELD: 0, NOT_QUALIFIED: 0, NOT_ATTEMPTED: 0}

    with io.open(SOURCE, encoding="utf-8-sig", newline="") as f:
        for i, row in enumerate(csv.DictReader(f), start=1):
            if args.limit is not None and i > args.limit:
                break

            email = (row.get("Work Email") or "").strip()
            domain = _domain_of(email)
            company = (row.get("Company") or "").strip() or domain or "?"

            if not domain:
                counts[NOT_QUALIFIED] += 1
                dispositions.append({
                    "row": i, "company": company, "domain": "",
                    "disposition": NOT_QUALIFIED,
                    "reason": "the source row carries no work email",
                    "admitted": 0, "attempted": False,
                })
                continue

            rec = by_domain.get(domain)
            if rec is None:
                counts[NOT_QUALIFIED] += 1
                dispositions.append({
                    "row": i, "company": company, "domain": domain,
                    "disposition": NOT_QUALIFIED,
                    "reason": "no canonical record for %s" % domain,
                    "admitted": 0, "attempted": False,
                })
                continue

            if not _eligible_for_research(rec):
                counts[NOT_QUALIFIED] += 1
                dispositions.append({
                    "row": i, "company": company, "domain": domain,
                    "disposition": NOT_QUALIFIED,
                    "reason": ("record state %r or rejected/no contacts"
                               % rec.get("state")),
                    "admitted": _admitted_count(rec), "attempted": False,
                })
                continue

            if _copy_sufficient(rec):
                counts[QUALIFIED] += 1
                dispositions.append({
                    "row": i, "company": company, "domain": domain,
                    "disposition": QUALIFIED,
                    "reason": ("evidence already sufficient (%d admitted)"
                               % _admitted_count(rec)),
                    "admitted": _admitted_count(rec), "attempted": False,
                })
                continue

            if not account_cap.allow(rec["id"]):
                counts[NOT_ATTEMPTED] += 1
                dispositions.append({
                    "row": i, "company": company, "domain": domain,
                    "disposition": NOT_ATTEMPTED,
                    "reason": "account cap reached (%d)" % args.cap,
                    "admitted": _admitted_count(rec), "attempted": False,
                })
                continue

            enrich.enrich_record(
                rec, budget, live=args.live, log=[], config=config,
                scrape_budget=scrape_budget, mx_cache=mx_cache,
                for_copy=True,
            )

            admitted = _admitted_count(rec)
            if _copy_sufficient(rec):
                counts[QUALIFIED] += 1
                dispositions.append({
                    "row": i, "company": company, "domain": domain,
                    "disposition": QUALIFIED,
                    "reason": "research reached the bar (%d admitted)" % admitted,
                    "admitted": admitted, "attempted": True,
                })
            else:
                counts[HELD] += 1
                dispositions.append({
                    "row": i, "company": company, "domain": domain,
                    "disposition": HELD,
                    "reason": ("insufficient admissible evidence after "
                               "research (%d admitted, needs %d)"
                               % (admitted, research.MIN_COPY_EVIDENCE_ROWS)),
                    "admitted": admitted, "attempted": True,
                })

    if args.live:
        store.save(recs)
        research.flush_crawl_cache()

    head = "LIVE" if args.live else "DRY RUN"
    print("%s: walked %d rows" % (head, len(dispositions)))
    print()
    for d in dispositions:
        mark = "*" if d["attempted"] else " "
        print("  %s %4d  %-12s %-30s %s" % (
            mark, d["row"], d["disposition"],
            d["company"][:28], d["reason"][:90]))
    print()
    print("qualified:     %d" % counts[QUALIFIED])
    print("held:          %d" % counts[HELD])
    print("not qualified: %d" % counts[NOT_QUALIFIED])
    print("not attempted: %d" % counts[NOT_ATTEMPTED])
    print("account cap:   %d started, %d refused" % (
        len(account_cap.started), len(account_cap.refused)))
    if account_cap.refused:
        print("  refused: %s" % ", ".join(account_cap.refused[:10]))

    return {
        "live": args.live, "dispositions": dispositions,
        "counts": counts, "account_cap": {
            "started": list(account_cap.started),
            "refused": list(account_cap.refused),
        },
        "budget_spent": budget.spent,
    }


if __name__ == "__main__":
    main()
