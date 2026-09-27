#!/usr/bin/env python3
"""A spend report the operator can act on.

TASK-352. The operator asked for a spend report and got three different numbers
from the same fifty leads, depending on which denominator was used. A report
that prints one cost-per-lead without naming its denominator invites the same
confusion.

WHAT THIS REPORTS

Per client and per day:
  - Spend per provider in that provider's own unit (credits, cents, microusd, ticks)
  - usd_estimate where a rate is established (None where nobody has priced it)
  - Cost per lead on THREE denominators, each labelled:
      * per cohort lead (all leads in the cohort)
      * per WRITTEN lead (leads that reached "pushed" state)
      * per lead passing BOTH gates (leads that are "approved" - sendable)

THE RULES

1. Never sum two units. Where units differ, print them separately and emit
   "MIXED UNITS - a tripwire, not an amount".
2. Never invent a rate. USD_PER_UNIT["credits"] is None because nobody has
   priced a credit. An unpriced provider reports usd_estimate: null and
   rate_source: "unknown".
3. Say what is NOT counted. Model rows currently carry client="_model" and
   there are _model rows already on disk that cannot be attributed. Report
   their count and total separately, as unattributed, rather than dropping
   or guessing them.

USAGE

    py -3 scripts/spend_report.py --client productive
    py -3 scripts/spend_report.py --client productive --day 2026-09-26
    py -3 scripts/spend_report.py --all-clients
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import clients, spendledger, store  # noqa: E402


def _count_leads(client, state_filter=None):
    """Count leads for this client, optionally filtered by state.

    The three denominators:
      - None (no filter): all cohort leads
      - "written": leads that passed the first gate (drafted, approved, or pushed)
      - "approved": leads passing both gates (approved or pushed)
    """
    try:
        rows = store.read_jsonl(store.queue_path())
    except FileNotFoundError:
        return 0
    
    # States that indicate passing the first gate (copylint)
    written_states = {"drafted", "approved", "pushed"}
    # States that indicate passing both gates (copylint + sequencegate)
    both_gates_states = {"approved", "pushed"}
    
    count = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get("client") != client:
            continue
        
        state = row.get("state")
        if state_filter == "written":
            if state not in written_states:
                continue
        elif state_filter == "approved":
            if state not in both_gates_states:
                continue
        elif state_filter and state != state_filter:
            continue
        
        count += 1
    return count


def _group_by_client_and_day(spend_rows):
    """Group spend rows by (client, day). Returns dict of dicts."""
    groups = {}
    for row in spend_rows:
        if not isinstance(row, dict):
            continue
        client = row.get("client")
        day = row.get("day")
        if not client or not day:
            continue
        key = (client, day)
        if key not in groups:
            groups[key] = []
        groups[key].append(row)
    return groups


def _summarize_provider(rows):
    """Summarize one provider's rows: total in native unit, usd_estimate, rate source."""
    by_unit = {}
    total_usd_estimate = 0.0
    has_usd_estimate = False
    rate_source = "unknown"

    for row in rows:
        cost = int(row.get("expected_cost") or 0)
        unit = spendledger.row_unit(row)
        by_unit[unit] = by_unit.get(unit, 0) + cost

        estimate = row.get("usd_estimate")
        if estimate is not None:
            total_usd_estimate += float(estimate)
            has_usd_estimate = True
            rate_source = row.get("rate_source", "unknown")

    return {
        "by_unit": by_unit,
        "usd_estimate": total_usd_estimate if has_usd_estimate else None,
        "rate_source": rate_source if has_usd_estimate else "unknown",
    }


def _report_one_client_day(client, day, spend_rows):
    """Build the report block for one (client, day) pair."""
    by_provider = {}
    unattributed_count = 0
    unattributed_cost = 0
    all_units = set()

    for row in spend_rows:
        # Unattributed _model rows (client='_model')
        if row.get("client") == "_model":
            unattributed_count += 1
            unattributed_cost += int(row.get("expected_cost") or 0)
            continue

        provider = row.get("provider")
        if not provider:
            continue

        if provider not in by_provider:
            by_provider[provider] = []
        by_provider[provider].append(row)
        all_units.add(spendledger.row_unit(row))

    # Summarize each provider
    provider_summaries = {}
    for provider, rows in sorted(by_provider.items()):
        provider_summaries[provider] = _summarize_provider(rows)

    # Lead counts for the three denominators
    cohort_leads = _count_leads(client)
    written_leads = _count_leads(client, state_filter="written")
    approved_leads = _count_leads(client, state_filter="approved")

    # Total spend in USD (only from providers with established rates)
    total_usd = sum(
        s["usd_estimate"]
        for s in provider_summaries.values()
        if s["usd_estimate"] is not None
    )

    # Cost per lead on three denominators
    cost_per_cohort_lead = (total_usd / cohort_leads) if cohort_leads > 0 else None
    cost_per_written_lead = (total_usd / written_leads) if written_leads > 0 else None
    cost_per_approved_lead = (total_usd / approved_leads) if approved_leads > 0 else None

    return {
        "client": client,
        "day": day,
        "providers": provider_summaries,
        "units_seen": sorted(all_units),
        "mixed_units": len(all_units) > 1,
        "total_usd_estimate": total_usd,
        "lead_counts": {
            "cohort_leads": cohort_leads,
            "written_leads": written_leads,
            "approved_leads": approved_leads,
        },
        "cost_per_lead": {
            "per_cohort_lead": cost_per_cohort_lead,
            "per_written_lead": cost_per_written_lead,
            "per_approved_lead": cost_per_approved_lead,
        },
        "unattributed_model_rows": {
            "count": unattributed_count,
            "total_cost": unattributed_cost,
        },
    }


def generate_report(client=None, day=None, all_clients=False):
    """Generate the spend report.

    Args:
        client: filter to this client
        day: filter to this day (YYYY-MM-DD)
        all_clients: if True, report all clients
    """
    spend_rows = spendledger.load()

    # Filter rows
    if client and not all_clients:
        spend_rows = [r for r in spend_rows if isinstance(r, dict) and r.get("client") == client]
    if day:
        spend_rows = [r for r in spend_rows if isinstance(r, dict) and r.get("day") == day]

    # Group by (client, day)
    groups = _group_by_client_and_day(spend_rows)

    # Build report for each group
    report_blocks = []
    for (cli, dy), rows in sorted(groups.items()):
        block = _report_one_client_day(cli, dy, rows)
        report_blocks.append(block)

    return {
        "generated_at": store.now(),
        "filter": {
            "client": client if not all_clients else "ALL",
            "day": day,
        },
        "blocks": report_blocks,
    }


def format_report(report):
    """Format the report for human reading."""
    lines = []
    lines.append(f"SPEND REPORT  generated={report['generated_at']}")
    lines.append(f"  filter: client={report['filter']['client']}, day={report['filter']['day'] or 'ALL'}")
    lines.append("")

    for block in report["blocks"]:
        lines.append(f"CLIENT: {block['client']}  DAY: {block['day']}")
        lines.append("=" * 70)

        # Per-provider breakdown
        lines.append("SPEND BY PROVIDER (in each provider's own unit):")
        for provider, summary in block["providers"].items():
            unit_parts = []
            for unit, total in sorted(summary["by_unit"].items()):
                unit_parts.append(f"{total} {unit}")
            units_str = " + ".join(unit_parts) if unit_parts else "0"

            usd_str = "null"
            if summary["usd_estimate"] is not None:
                usd_str = f"${summary['usd_estimate']:.4f}"
                if summary["rate_source"]:
                    usd_str += f" (rate_source: {summary['rate_source']})"

            lines.append(f"  {provider:<20} {units_str:<30} usd_estimate: {usd_str}")

        if block["mixed_units"]:
            lines.append("")
            lines.append(f"  MIXED UNITS - a tripwire, not an amount")
            lines.append(f"  (units seen: {', '.join(block['units_seen'])})")

        # Unattributed model rows
        if block["unattributed_model_rows"]["count"] > 0:
            lines.append("")
            lines.append("UNATTRIBUTED MODEL ROWS (client='_model'):")
            lines.append(f"  count: {block['unattributed_model_rows']['count']}")
            lines.append(f"  total_cost: {block['unattributed_model_rows']['total_cost']}")

        # Lead counts
        lines.append("")
        lines.append("LEAD COUNTS (three denominators):")
        lc = block["lead_counts"]
        lines.append(f"  cohort leads (all):              {lc['cohort_leads']}")
        lines.append(f"  written leads (state='pushed'):  {lc['written_leads']}")
        lines.append(f"  approved leads (both gates):     {lc['approved_leads']}")

        # Cost per lead
        lines.append("")
        lines.append("COST PER LEAD (labelled by denominator):")
        cpl = block["cost_per_lead"]
        if cpl["per_cohort_lead"] is not None:
            lines.append(f"  per cohort lead:  ${cpl['per_cohort_lead']:.4f}")
        else:
            lines.append(f"  per cohort lead:  N/A (no cohort leads)")

        if cpl["per_written_lead"] is not None:
            lines.append(f"  per written lead: ${cpl['per_written_lead']:.4f}")
        else:
            lines.append(f"  per written lead: N/A (no written leads)")

        if cpl["per_approved_lead"] is not None:
            lines.append(f"  per approved lead (both gates): ${cpl['per_approved_lead']:.4f}")
        else:
            lines.append(f"  per approved lead (both gates): N/A (no approved leads)")

        lines.append("")
        lines.append("")

    return "\n".join(lines)


def main(argv=None):
    p = argparse.ArgumentParser(
        description="A spend report the operator can act on.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__)
    p.add_argument("--client", help="Filter to this client")
    p.add_argument("--day", help="Filter to this day (YYYY-MM-DD)")
    p.add_argument("--all-clients", action="store_true",
                   help="Report all clients")
    p.add_argument("--json", action="store_true",
                   help="Output as JSON")
    args = p.parse_args(argv)

    if not args.client and not args.all_clients:
        p.error("either --client or --all-clients is required")

    report = generate_report(
        client=args.client,
        day=args.day,
        all_clients=args.all_clients)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(format_report(report))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
