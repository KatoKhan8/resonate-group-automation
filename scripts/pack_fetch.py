#!/usr/bin/env python3
"""Chunked, resumable, cost-capped research pack fetch.

    py -3 scripts/pack_fetch.py --chunk 25 --max-chunks 1
    py -3 scripts/pack_fetch.py --chunk 25 --max-chunks 1   # resume: buys 0
    py -3 scripts/pack_fetch.py --report
    py -3 scripts/pack_fetch.py --budget-usd 0.10 --chunk 25  # refuses

Reads the S3 ICP "IN" set, journals per-domain as it goes, and resumes
from the journal on restart. A chunk whose projected cost crosses the
budget is REFUSED before a single actor starts - truncation is not
success.

THE WEBSITE CRAWLER IS OFF. Operator, 2026-09-24: "site content comes
from our own free crawler, and Apify runs LinkedIn only." The default
path runs company_posts and open_roles (LinkedIn actors only). Turning
on the website crawler requires --website-crawler-ok, which names the
operator ruling it overrides.

EVERY PAID CALL goes through spendledger via researchpack.build. The
spend ledger gains one row per actor run, and the coverage report sums
those rows - if they disagree, the report is wrong, not the ledger.
"""
import argparse
import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import researchpack, spendledger                      # noqa: E402
from src.researchpack import cache as pack_cache               # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: The S3 ICP amended file: the 19,612 "IN" domains.
DEFAULT_INPUT = os.path.join(
    ROOT, "work", "stage", "s3-icp-amended-PRODUCTIVE-2026-09-07.jsonl")

#: LinkedIn-only planned cost per account, in cents.
#: company_posts (5) + open_roles (4) = 9. This is the FALLBACK when the
#: spend ledger has no measured Apify rows to compute from.
LINKEDIN_ONLY_CENTS = 9

#: Environment override for the per-account cost used in budget projections.
#: Tests set this to control the refusal threshold without seeding a ledger.
COST_OVERRIDE_VAR = "PACK_FETCH_COST_PER_ACCOUNT_CENTS"


def load_input_domains(path):
    """Domains with S3 ICP verdict 'in', from the amended JSONL.

    Returns a sorted, deduplicated list. The file format is one JSON object
    per line with at least 'domain' and 'verdict' fields - the same file
    `scripts/stage_mx_amended.py` and `scripts/batch_eligibility.py` read.
    """
    domains = set()
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if str(row.get("verdict") or "").lower() == "in":
                d = str(row.get("domain") or "").strip().lower()
                if d:
                    domains.add(d)
    return sorted(domains)


def load_journal(path):
    """Read the journal. Last write per domain wins (same as stage_mx)."""
    out = {}
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            d = row.get("domain")
            if d:
                out[d] = row
    return out


def append_journal(path, entry):
    """Append one domain's result. Flush immediately - a dead process
    that wrote nothing has lost everything."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, default=str) + "\n")


def cost_per_account_cents():
    """Measured cost per account in cents, for budget projections.

    Priority:
    1. PACK_FETCH_COST_PER_ACCOUNT_CENTS env (tests, operator override)
    2. Spend ledger's measured Apify rows (actual rate from past runs)
    3. Planned LinkedIn-only cost: company_posts (5) + open_roles (4) = 9

    The task names the measured rate at $0.03987/account (3.987 cents).
    When the ledger has rows, we use that actual figure. When it does not,
    we fall back to the planned LinkedIn-only cost.
    """
    override = os.environ.get(COST_OVERRIDE_VAR, "").strip()
    if override:
        return float(override)
    rows = spendledger.load()
    apify_rows = [r for r in rows if r.get("provider") == "apify"]
    if apify_rows:
        total_cents = sum(int(r.get("expected_cost") or 0) for r in apify_rows)
        domains = len({r.get("call", "") for r in apify_rows})
        # Each account runs 2 LinkedIn actors (company_posts + open_roles),
        # so the number of accounts is roughly len(apify_rows) / 2.
        accounts = max(len(apify_rows) // 2, 1)
        return total_cents / accounts
    return LINKEDIN_ONLY_CENTS


def check_budget(budget_usd, chunk_size, rate_cents):
    """Refuse if the projected cost of one chunk crosses the ceiling.

    Returns (projected_usd, rate_usd, refused: bool). The projection is
    `measured cost/account x accounts in the chunk`, not an estimate from
    a price page. Crossing is a refusal with the numbers in it, never a
    truncation that reports success.
    """
    rate_usd = rate_cents / 100.0
    projected = rate_usd * chunk_size
    return projected, rate_usd, projected > budget_usd


def fetch(args):
    """Main fetch loop. Returns the journal dict."""
    if args.website_crawler_ok:
        print("REFUSED: --website-crawler-ok is set, but the operator ruled "
              "on 2026-09-24 that site content comes from our own free "
              "crawler and Apify runs LinkedIn only. This flag overrides "
              "that ruling and is not enabled in this build.")
        return {}

    domains = load_input_domains(args.input)
    print(f"input set: {args.input}")
    print(f"  {len(domains):,} domains with S3 ICP verdict 'in'")

    work_dir = args.work_dir or os.path.join(ROOT, "work")
    journal_path = os.path.join(work_dir, "pack-fetch-journal.jsonl")
    os.makedirs(work_dir, exist_ok=True)

    journal = load_journal(journal_path)
    done = set(journal.keys())
    print(f"journal: {journal_path}")
    print(f"  {len(done):,} domains already resolved")

    if args.report:
        return report(domains, journal, work_dir)

    remaining = [d for d in domains if d not in done]
    if not remaining:
        print("bought 0 - all domains already in journal")
        return journal

    rate_cents = cost_per_account_cents()

    chunk_size = min(args.chunk, len(remaining))
    n_chunks = min(args.max_chunks,
                   (len(remaining) + chunk_size - 1) // chunk_size)

    if args.budget_usd is not None:
        projected, rate_usd, refused = check_budget(
            args.budget_usd, chunk_size, rate_cents)
        if refused:
            print(f"\nREFUSED: chunk of {chunk_size} accounts at "
                  f"${rate_usd:.5f}/account projects to "
                  f"${projected:.4f}, which exceeds the "
                  f"${args.budget_usd:.4f} budget.")
            print(f"  projected: ${projected:.4f}")
            print(f"  budget:    ${args.budget_usd:.4f}")
            print(f"  rate:      ${rate_usd:.5f}/account")
            return journal

    total_bought = 0
    total_refused = 0
    total_errors = 0
    total_cost_cents = 0
    offset = 0

    for chunk_idx in range(n_chunks):
        chunk = remaining[offset:offset + chunk_size]
        if not chunk:
            break
        offset += chunk_size
        print(f"\n--- chunk {chunk_idx + 1}/{n_chunks}: "
              f"{len(chunk)} domains ---")

        for d in chunk:
            try:
                pack = researchpack.build(
                    d, live=True, client=args.client,
                    runner=args.runner if hasattr(args, "runner") else None,
                    config=args.config if hasattr(args, "config") else None)
                cost = pack.get("cost", 0)
                entry = {
                    "domain": d,
                    "status": "ok",
                    "facts": pack.get("fact_count", 0),
                    "cost_cents": cost,
                    "bought": pack.get("bought", []),
                    "cached": pack.get("cached", []),
                }
                total_cost_cents += cost
                total_bought += 1
                print(f"  {d}: {pack.get('fact_count', 0)} facts, "
                      f"{cost}c, bought={pack.get('bought', [])}")
            except researchpack.PackRefused as e:
                entry = {"domain": d, "status": "refused",
                         "reason": str(e)}
                total_refused += 1
                print(f"  {d}: REFUSED - {e}")
            except Exception as e:
                entry = {"domain": d, "status": "error",
                         "reason": str(e)}
                total_errors += 1
                print(f"  {d}: ERROR - {e}")
            append_journal(journal_path, entry)
            journal[d] = entry

    print(f"\ndone: {total_bought} built, {total_refused} refused, "
          f"{total_errors} errors")
    print(f"cost: {total_cost_cents}c "
          f"(${total_cost_cents / 100.0:.4f})")
    return journal


def report(input_domains, journal, work_dir):
    """Coverage report. Attach to a push."""
    data = pack_cache.load()
    covered = set()
    for d in input_domains:
        entry = data.get(pack_cache.key_for(d))
        if entry and pack_cache._fresh(entry):
            facts = entry.get("facts") or []
            if any(f.get("source_url") for f in facts):
                covered.add(d)

    missing = set(input_domains) - covered - set(journal.keys())
    refused = {d for d, r in journal.items() if r.get("status") == "refused"}
    errors = {d for d, r in journal.items() if r.get("status") == "error"}
    ok = {d for d, r in journal.items() if r.get("status") == "ok"}

    rows = spendledger.load()
    apify_rows = [r for r in rows if r.get("provider") == "apify"]
    spent_cents = sum(int(r.get("expected_cost") or 0) for r in apify_rows)
    spent_usd = spent_cents * spendledger.USD_PER_UNIT.get("cents", 0.01)

    total_ok = len(ok)
    rate = spent_usd / total_ok if total_ok > 0 else 0
    remaining = len(input_domains) - total_ok - len(refused) - len(errors)
    projected = rate * remaining if rate > 0 else 0

    print(f"\n=== PACK COVERAGE REPORT ===")
    print(f"  input domains:     {len(input_domains):,}")
    print(f"  packs present:     {len(covered):,}")
    print(f"  packs missing:     {len(missing):,}")
    print(f"  packs refused:     {len(refused):,}")
    print(f"  packs errored:     {len(errors):,}")
    print(f"  journal ok:        {len(ok):,}")
    print(f"  USD spent to date: ${spent_usd:.4f}")
    if total_ok > 0:
        print(f"  USD/account actual: ${rate:.5f}")
    else:
        print(f"  USD/account actual: N/A (no packs built yet)")
    print(f"  projected total for remaining {remaining:,} "
          f"at actual rate: ${projected:.4f}")
    print(f"  projected total for 19,612 at actual rate: "
          f"${rate * 19612:.4f}")
    return journal


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__.splitlines()[0])
    ap.add_argument("--chunk", type=int, default=25,
                    help="accounts per chunk (default: 25)")
    ap.add_argument("--max-chunks", type=int, default=1,
                    help="max chunks per run (default: 1)")
    ap.add_argument("--budget-usd", type=float, default=None,
                    help="refuse if projected chunk cost exceeds this")
    ap.add_argument("--work-dir", default=None,
                    help="journal directory (default: work/)")
    ap.add_argument("--input", default=DEFAULT_INPUT,
                    help="S3 ICP amended JSONL")
    ap.add_argument("--website-crawler-ok", action="store_true",
                    help="override operator ruling: 'Apify runs LinkedIn "
                         "only'. Currently refuses - website crawler is "
                         "not in this module.")
    ap.add_argument("--client", default="productive")
    ap.add_argument("--report", action="store_true",
                    help="print coverage report and exit")
    args = ap.parse_args(argv)
    fetch(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
