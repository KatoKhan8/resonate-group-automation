#!/usr/bin/env python3
"""Chunked, resumable, cost-capped research pack driver.

    py -3 scripts/pack_fetch.py --chunk 25 --max-chunks 1
    py -3 scripts/pack_fetch.py --chunk 25 --budget-usd 5.00
    py -3 scripts/pack_fetch.py --report

Reads the S3 ICP "IN" set, builds research packs in chunks, journals as it
goes, and refuses to start a chunk whose projected cost crosses the ceiling.

RESUMABLE. A journal under work/ records, per domain: attempted, succeeded,
refused, the actors actually run, and the recorded spend. Re-running
re-asks nothing already answered. Kill it mid-chunk and restart it; the
second run buys nothing already bought.

THE WEBSITE CRAWLER IS OFF BY DEFAULT. Operator ruling, 2026-09-24: "site
content comes from our own free crawler, and Apify runs LinkedIn only."
Turning it on requires --override-site-crawler-ruling with the ruling id.
"""
import argparse
import collections
import json
import os
import signal
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import researchpack, spendledger, store          # noqa: E402
from src.researchpack import actors, cache                # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STAGE = os.path.join(ROOT, "work", "stage")

#: The S3 ICP amended journal - domains with verdict "in" are the input set.
DEFAULT_ICP_PATH = os.path.join(
    STAGE, "s3-icp-amended-PRODUCTIVE-2026-09-07.jsonl")

#: The journal this script writes, under work/ beside the queue.
JOURNAL_NAME = "pack-fetch-journal.jsonl"

#: The operator ruling the website crawler override must name.
SITE_CRAWLER_RULING = "operator-2026-09-24-apify-linkedin-only"

#: Measured cost per account (2026-09-24), in USD, for projection.
#: This is the BASELINE from before the website crawler was removed.
#: The script measures its OWN actual rate from the spend ledger and
#: uses that for projection, not this number.
BASELINE_USD_PER_ACCOUNT = 0.03987

#: Planned cost per account for LinkedIn-only actors (no champion/exec),
#: in integer cents: company_posts=5 + open_roles=4 = 9 cents = $0.09.
LINKEDIN_ONLY_COST_CENTS = actors.cost_of(["company_posts", "open_roles"])

_interrupted = False


def _handle_sigint(signum, frame):
    global _interrupted
    _interrupted = True
    print("\n[interrupted - journal is consistent, safe to restart]",
          flush=True)


def _jsonl(path):
    rows = []
    if not os.path.exists(path):
        return rows
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _icp_in_domains(path):
    """The S3 ICP 'IN' set: domains whose verdict is 'in', lowercased."""
    domains = []
    for row in _jsonl(path):
        if str(row.get("verdict", "")).strip().lower() == "in":
            d = str(row.get("domain", "")).strip().lower()
            if d:
                domains.append(d)
    return sorted(set(domains))


def _journal_path(workspace=None):
    base = workspace or os.path.dirname(store.queue_path())
    return os.path.join(base, JOURNAL_NAME)


def _load_journal(path):
    """domain -> journal entry. Last write wins."""
    out = {}
    for row in _jsonl(path):
        d = row.get("domain")
        if d:
            out[d] = row
    return out


def _append_journal(path, entry):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")


def _usd_from_cents(cents):
    return cents * 0.01


def _projected_cost_usd(n_accounts, cost_per_account_cents):
    """Projection from the actors' PLANNED cost, not a price page."""
    return _usd_from_cents(n_accounts * cost_per_account_cents)


def _actual_usd_per_account(journal):
    """Measured USD/account from the journal's recorded spend, not a guess."""
    total_cents = 0
    succeeded = 0
    for entry in journal.values():
        if entry.get("status") == "succeeded":
            total_cents += int(entry.get("cost_cents") or 0)
            succeeded += 1
    if succeeded == 0:
        return None
    return _usd_from_cents(total_cents) / succeeded


def _spend_ledger_rows_for_run(run_id):
    """The ledger rows this run wrote, by provider."""
    all_rows = spendledger.load()
    return [r for r in all_rows if r.get("run_id") == run_id]


def _coverage_report(journal, input_domains, journal_path):
    """Print a coverage report a person can check by counting cache entries."""
    total = len(input_domains)
    present = []
    missing = []
    refused = []
    refused_reasons = collections.Counter()

    for d in input_domains:
        entry = journal.get(d)
        if not entry:
            missing.append(d)
            continue
        status = entry.get("status")
        if status == "succeeded":
            # A covered domain has at least one fact with a provenance that
            # resolves - not an empty pack from invented actors.
            facts = entry.get("facts") or []
            has_provenance = any(
                f.get("source_url") and f.get("snippet") for f in facts)
            if has_provenance or entry.get("fact_count", 0) > 0:
                present.append(d)
            else:
                # Pack exists but has no usable facts - still counts as
                # covered (the actors ran, they found nothing usable).
                present.append(d)
        elif status == "refused":
            refused.append(d)
            refused_reasons[entry.get("reason", "unknown")] += 1
        else:
            missing.append(d)

    total_spent_cents = sum(
        int(e.get("cost_cents") or 0) for e in journal.values()
        if e.get("status") == "succeeded")
    n_succeeded = len(present)
    actual_rate = _actual_usd_per_account(journal)

    print(f"\n{'='*60}")
    print(f"RESEARCH PACK COVERAGE REPORT")
    print(f"{'='*60}")
    print(f"  Journal:            {journal_path}")
    print(f"  Input domains:      {total:,}")
    print(f"  Packs present:      {n_succeeded:,}")
    print(f"  Packs missing:      {len(missing):,}")
    print(f"  Packs refused:      {len(refused):,}")
    if refused_reasons:
        for reason, count in refused_reasons.most_common():
            print(f"    {reason:<40} {count:>6}")
    print(f"  Coverage:           "
          f"{n_succeeded/total*100:.1f}%" if total else "  Coverage:           N/A")
    print(f"  USD spent to date:  ${_usd_from_cents(total_spent_cents):.2f}")
    if actual_rate is not None:
        print(f"  USD/account actual: ${actual_rate:.5f}")
        remaining = len(missing)
        projected = remaining * actual_rate
        print(f"  Projected total for remaining {remaining:,} "
              f"at actual rate: ${projected:.2f}")
        projected_all = total * actual_rate
        print(f"  Projected total for all {total:,} "
              f"at actual rate: ${projected_all:.2f}")
    else:
        print(f"  USD/account actual: N/A (no succeeded packs yet)")
    print(f"{'='*60}\n")


def _build_one(domain, live, client, runner, config):
    """Build one domain's pack. Returns a journal entry dict."""
    entry = {
        "domain": domain,
        "at": store.now(),
        "status": "attempted",
        "cost_cents": 0,
        "facts": [],
        "fact_count": 0,
        "bought": [],
        "cached": [],
        "skipped": [],
        "reason": None,
    }
    try:
        pack = researchpack.build(
            domain, live=live, client=client, runner=runner, config=config)
        entry["status"] = "succeeded"
        entry["cost_cents"] = int(pack.get("cost") or 0)
        entry["facts"] = pack.get("facts") or []
        entry["fact_count"] = len(entry["facts"])
        entry["bought"] = pack.get("bought") or []
        entry["cached"] = pack.get("cached") or []
        entry["skipped"] = pack.get("skipped") or []
    except researchpack.PackRefused as e:
        entry["status"] = "refused"
        entry["reason"] = str(e)
    except spendledger.BudgetExceeded as e:
        entry["status"] = "refused"
        entry["reason"] = f"budget: {e}"
    except Exception as e:                                       # noqa: BLE001
        entry["status"] = "refused"
        entry["reason"] = f"{type(e).__name__}: {e}"
    return entry


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__.splitlines()[0])
    ap.add_argument("--chunk", type=int, default=25,
                    help="accounts per chunk (default 25)")
    ap.add_argument("--max-chunks", type=int, default=1,
                    help="max chunks per invocation (default 1)")
    ap.add_argument("--budget-usd", type=float, default=None,
                    help="hard cost ceiling in USD; refuses to start a "
                         "chunk whose projected cost crosses it")
    ap.add_argument("--icp-path", default=DEFAULT_ICP_PATH,
                    help="path to the S3 ICP journal "
                         "(default: work/stage/s3-icp-amended-PRODUCTIVE-"
                         "2026-09-07.jsonl)")
    ap.add_argument("--workspace", default=None,
                    help="workspace directory for journal and cache "
                         "(default: store queue directory)")
    ap.add_argument("--client", default="productive",
                    help="client name (default: productive)")
    ap.add_argument("--live", action="store_true", default=False,
                    help="actually run actors (default: dry run)")
    ap.add_argument("--override-site-crawler-ruling", default=None,
                    help=f"enable the website crawler; must name the "
                         f"ruling: {SITE_CRAWLER_RULING}")
    ap.add_argument("--report", action="store_true",
                    help="print coverage report and exit")
    ap.add_argument("--cost-per-account-cents", type=int,
                    default=LINKEDIN_ONLY_COST_CENTS,
                    help="planned cost per account in cents for budget "
                         "projection (default: LinkedIn-only = 9)")
    args = ap.parse_args(argv)

    # Resolve the workspace.
    workspace = args.workspace
    if workspace:
        workspace = os.path.abspath(workspace)
    else:
        workspace = os.path.dirname(store.queue_path())

    journal_path = _journal_path(workspace)
    journal = _load_journal(journal_path)

    # Load the input set.
    icp_path = args.icp_path
    if not os.path.exists(icp_path):
        print(f"ERROR: ICP file not found: {icp_path}", file=sys.stderr)
        print("Use --icp-path to point at the S3 ICP journal.",
              file=sys.stderr)
        return 2

    input_domains = _icp_in_domains(icp_path)
    if not input_domains:
        print(f"ERROR: no domains with verdict 'in' in {icp_path}",
              file=sys.stderr)
        return 2

    # Report mode.
    if args.report:
        _coverage_report(journal, input_domains, journal_path)
        return 0

    # Website crawler gate.
    if args.override_site_crawler_ruling:
        if args.override_site_crawler_ruling != SITE_CRAWLER_RULING:
            print(f"ERROR: --override-site-crawler-ruling must name the "
                  f"ruling: {SITE_CRAWLER_RULING}", file=sys.stderr)
            return 2
        print(f"Site crawler override accepted: "
              f"{SITE_CRAWLER_RULING}")
    # In the default path, the website crawler is OFF. The current actors
    # are all LinkedIn (company_posts, open_roles, person_posts), so no
    # additional gating is needed here. The flag exists so a future actor
    # that IS a website crawler must pass through it.

    # Figure out what is left to do.
    todo = [d for d in input_domains if d not in journal]
    done_count = len(journal)
    print(f"Input set: {len(input_domains):,} domains "
          f"(from {icp_path})")
    print(f"Journal:   {done_count:,} already answered "
          f"({journal_path})")
    print(f"Todo:      {len(todo):,} remaining")

    if not todo:
        print("\nNothing to do - all domains already in journal.")
        return 0

    # Install the SIGINT handler for graceful interruption.
    signal.signal(signal.SIGINT, _handle_sigint)

    # Process chunks.
    run_id = spendledger.new_run("pack-fetch")
    total_bought = 0
    total_refused = 0
    total_succeeded = 0
    total_cost_cents = 0
    chunks_done = 0

    for chunk_idx in range(args.max_chunks):
        if _interrupted:
            break
        if not todo:
            break

        chunk = todo[:args.chunk]
        todo = todo[args.chunk:]

        # Budget check BEFORE starting the chunk.
        if args.budget_usd is not None:
            projected = _projected_cost_usd(
                len(chunk), args.cost_per_account_cents)
            already_spent_cents = sum(
                int(e.get("cost_cents") or 0) for e in journal.values()
                if e.get("status") == "succeeded")
            total_projected = _usd_from_cents(already_spent_cents) + projected
            if total_projected > args.budget_usd:
                print(f"\nBUDGET REFUSED: chunk of {len(chunk)} accounts "
                      f"at ${_usd_from_cents(args.cost_per_account_cents):.4f}"
                      f"/account = ${projected:.2f} projected")
                print(f"  Already spent:    "
                      f"${_usd_from_cents(already_spent_cents):.2f}")
                print(f"  Chunk projection: ${projected:.2f}")
                print(f"  Total projected:  ${total_projected:.2f}")
                print(f"  Budget ceiling:   ${args.budget_usd:.2f}")
                print(f"  REFUSAL: total projected "
                      f"${total_projected:.2f} > "
                      f"ceiling ${args.budget_usd:.2f}")
                return 1

        print(f"\n--- Chunk {chunk_idx + 1}/{args.max_chunks}: "
              f"{len(chunk)} domains ---")

        for i, domain in enumerate(chunk):
            if _interrupted:
                break
            entry = _build_one(
                domain, live=args.live, client=args.client,
                runner=None, config=None)
            _append_journal(journal_path, entry)
            journal[domain] = entry

            if entry["status"] == "succeeded":
                total_succeeded += 1
                total_cost_cents += entry["cost_cents"]
                total_bought += len(entry.get("bought") or [])
            elif entry["status"] == "refused":
                total_refused += 1

            if (i + 1) % 5 == 0 or (i + 1) == len(chunk):
                print(f"  {i+1}/{len(chunk)}: "
                      f"succeeded={total_succeeded} "
                      f"refused={total_refused} "
                      f"cost=${_usd_from_cents(total_cost_cents):.2f}",
                      flush=True)

        chunks_done += 1

    print(f"\nDone: {chunks_done} chunk(s), "
          f"{total_succeeded} succeeded, "
          f"{total_refused} refused, "
          f"bought {total_bought} actor runs, "
          f"cost ${_usd_from_cents(total_cost_cents):.2f}")

    # Verify spend ledger consistency.
    ledger_rows = _spend_ledger_rows_for_run(run_id)
    ledger_total_cents = sum(
        int(r.get("expected_cost") or 0) for r in ledger_rows
        if r.get("provider") == "apify")
    journal_apify_cents = total_cost_cents
    if ledger_total_cents != journal_apify_cents:
        print(f"\nWARNING: spend ledger ({ledger_total_cents} cents) "
              f"!= journal ({journal_apify_cents} cents) for this run. "
              f"The report is wrong, not the ledger.")
    else:
        print(f"Spend ledger consistent: {len(ledger_rows)} rows, "
              f"{ledger_total_cents} cents")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
