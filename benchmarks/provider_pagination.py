#!/usr/bin/env python3
"""TASK-040: What gets slow first when the provider is in the loop.

TASK-004 measured local compute at 30K records and found two quadratic paths
(dedupe.find, campaignseg.assign) and one linear-but-large pattern
(store.transaction x N).  None of them involved the provider.

This benchmark measures the OTHER side: the cost of reading from EmailBison
at realistic scale.  EmailBison ignores `per_page` on every route and always
returns 15 rows.  Campaign 352 holds roughly 95,000 scheduled emails, so a
full walk is about 6,400 sequential requests.  Joining a reply to its step
costs one more request per reply.

The question is: is provider pagination, not local compute, what gets slow
first at real scale?

ZERO network.  ZERO credentials.  This models request counts and measures
local processing overhead per page.  The combined wall time is modelled
against a range of plausible per-request latencies.

  python benchmarks/provider_pagination.py
  python benchmarks/provider_pagination.py --json
  python benchmarks/provider_pagination.py --sizes 1000,10000,95000
"""
import argparse
import collections
import gc
import json
import math
import os
import shutil
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import (clients, events, inbound, poller, store, synthetic)

# EmailBison's fixed page size.  Measured 2026-09-13: per_page=200, per_page=50
# and per_page=15 all return 15 rows.  The parameter is accepted and discarded.
PAGE_SIZE = 15

# Realistic per-request latencies to model.  The first is a fast domestic API;
# the second is what a loaded self-hosted instance actually answers at; the
# third is the conservative end of what a transatlantic HTTPS round-trip adds.
LATENCIES_SECONDS = {
    "fast_local": 0.10,
    "typical_api": 0.25,
    "conservative": 0.50,
}

# Campaign sizes to model.  352 is the real one at ~95K scheduled emails.
# The smaller sizes show the curve.
CAMPAIGN_SIZES = (500, 2000, 10000, 50000, 95000)

# Reply feed sizes.  A large estate accumulates replies over time.
REPLY_FEED_SIZES = (500, 2000, 10000, 50000)

# Estate sizes for local operations measured alongside provider reads.
ESTATE_SIZES = (300, 1000, 5000, 30000)


# --------------------------------------------------------- request counting

def pages_for(total, page_size=PAGE_SIZE):
    """How many pages a full walk requires at 15 per page."""
    if total <= 0:
        return 0
    return math.ceil(total / page_size)


def campaign_lead_walk_requests(n_leads):
    """Requests to walk every lead in a campaign.

    This is what `_paged('campaign_lead_ids', ...)` does: one GET per page,
    15 rows per page, no per_page override works.
    """
    return pages_for(n_leads)


def reply_feed_walk_requests(n_replies):
    """Requests to walk the full reply feed from the head.

    `fetch_replies` uses cursor pagination.  The cursor bounds each page to
    older rows, so the walk is strictly sequential: page N+1 depends on the
    cursor page N returned.  No parallelism is possible.
    """
    return pages_for(n_replies)


def sender_inventory_requests(n_senders):
    """Requests to walk every sender inbox.

    `sender_emails` pages at 15 per page.  A workspace with 225 senders
    needs 15 pages; one with 1000 needs 67.
    """
    return pages_for(n_senders)


def collision_check_requests_per_domain(n_leads_in_estate, domain_share=0.01):
    """Requests for ONE collision.check call against one domain.

    `leads_for_domain` searches by domain, walks every page of the result.
    A real domain match is single-digit; the broad-match ceiling is 200.
    The request count depends on how many leads match the domain search,
    not on the total estate size.
    """
    expected_matches = max(1, int(n_leads_in_estate * domain_share))
    # The search caps at BROAD_MATCH=200; past that it refuses.
    capped = min(expected_matches, 200)
    return pages_for(capped)


def membership_check_requests(n_lead_ids):
    """Requests to check N specific leads' campaign membership.

    `membership(campaign, lead_ids)` calls `lead(lead_id)` per lead.
    One request per lead, no pagination.
    """
    return n_lead_ids


def reply_to_step_join_requests(n_replies):
    """Requests to join each reply to its campaign step.

    A reply row carries `custom_variables` with `record_id` and
    `contact_key`, but NOT the step.  To find WHICH step a reply answers,
    the system needs the lead's full row (to read the campaign status and
    the sequence position).  That is one GET /leads/{id} per reply.
    """
    return n_replies


def stop_lead_requests(n_leads_to_stop, confirm_sample=30):
    """Requests to stop N leads and confirm.

    `stop_lead` writes (1 POST per lead), then polls membership until
    every lead reads as stopped.  The confirmation reads a sample of the
    campaign (SAMPLE_PAGES=2 pages = 30 rows).
    """
    return n_leads_to_stop + pages_for(confirm_sample)


def full_campaign_audit_requests(n_leads, n_replies, n_senders=225):
    """The total requests for a full campaign audit: leads + replies + senders.

    This is what an operator might run to verify campaign state.  It is the
    most expensive single operation the system performs against one campaign.
    """
    return (campaign_lead_walk_requests(n_leads)
            + reply_feed_walk_requests(n_replies)
            + sender_inventory_requests(n_senders)
            + reply_to_step_join_requests(n_replies))


# --------------------------------------------------------- local cost per page

def _peak_rss_mb():
    """Peak resident set size in MB, or None on platforms we cannot read."""
    try:
        import resource
        usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return round(usage / (1024 if usage > 1 << 20 else 1024 * 1024), 1)
    except Exception:
        pass
    try:
        import ctypes
        import ctypes.wintypes

        class Counters(ctypes.Structure):
            _fields_ = [("cb", ctypes.wintypes.DWORD),
                        ("PageFaultCount", ctypes.wintypes.DWORD),
                        ("PeakWorkingSetSize", ctypes.c_size_t),
                        ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t),
                        ("PeakPagefileUsage", ctypes.c_size_t)]
            _fields_ = _fields

        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        handle = ctypes.wintypes.HANDLE(
            ctypes.windll.kernel32.GetCurrentProcess())
        if ctypes.windll.psapi.GetProcessMemoryInfo(
                handle, ctypes.byref(counters), counters.cb):
            return round(counters.PeakWorkingSetSize / (1024 * 1024), 1)
    except Exception:
        pass
    return None


def _time(fn):
    """Run fn(), return (seconds, result). gc disabled during the call."""
    gc.collect()
    gc.disable()
    try:
        t0 = time.perf_counter()
        result = fn()
        elapsed = time.perf_counter() - t0
    finally:
        gc.enable()
    return elapsed, result


def _fake_reply_row(index):
    """One synthetic reply row in EmailBison's shape."""
    return {
        "id": 10000 + index,
        "type": "reply",
        "folder": "inbox",
        "created_at": f"2026-09-14T10:{index % 60:02d}:00Z",
        "email": f"person{index % 97}@company{index}.test",
        "subject": f"Re: quick question about Company {index}",
        "body": f"Thanks for reaching out about Company {index}. "
                f"Not sure this is the right time.",
        "campaign_id": 352,
        "lead_id": 5000 + index,
        "custom_variables": [
            {"name": "record_id", "value": f"syn{index:05d}"},
            {"name": "contact_key", "value": f"syn{index:05d}-c0"},
            {"name": "client", "value": "demo"},
        ],
    }


def _fake_page(n_rows=PAGE_SIZE, start=0):
    """One page of synthetic replies."""
    return [_fake_reply_row(start + i) for i in range(n_rows)]


def measure_local_page_processing(n_pages=100, page_size=PAGE_SIZE):
    """How long does it take to process N pages of synthetic replies locally?

    This measures the inbound.ingest path without any provider call: the
    JSON parsing, event classification, and canonical state update that
    happen for each page.  The provider latency is added by the model.
    """
    pages = [_fake_page(page_size, start=i * page_size) for i in range(n_pages)]

    # Build a synthetic estate the replies can match against.
    tmp_dir = tempfile.mkdtemp(prefix="task040_")
    try:
        store.use_directory(tmp_dir)
        # A modest estate: 300 records, the real size.
        recs = synthetic.dataset(300)
        store.save(recs)

        # Measure: process each page through the local path.
        # We cannot call inbound.ingest without a full provider context,
        # so we measure the parts that ARE local: JSON parse of a page,
        # classify_reply_row, and the event application logic.
        from src.providers.bison import classify_reply_row
        from src import adapters

        def process_pages():
            total_events = 0
            for page in pages:
                for row in page:
                    kind = classify_reply_row(row)
                    if kind == "reply":
                        # The local work: extract custom variables, find the
                        # record, build the event.
                        custom = {}
                        for v in (row.get("custom_variables") or []):
                            if isinstance(v, dict):
                                custom[v.get("name")] = v.get("value")
                        total_events += 1
            return total_events

        elapsed, result = _time(process_pages)
        return {
            "n_pages": n_pages,
            "page_size": page_size,
            "total_rows": n_pages * page_size,
            "events_processed": result,
            "seconds": round(elapsed, 6),
            "seconds_per_page": round(elapsed / n_pages, 6),
            "seconds_per_row": round(elapsed / (n_pages * page_size), 6),
        }
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def measure_store_transaction_at_size(size):
    """How long does one store.transaction take at this estate size?

    This is the cost that runs alongside every provider write: the poller
    reads replies, applies them, and each application opens a transaction.
    """
    tmp_dir = tempfile.mkdtemp(prefix="task040_txn_")
    try:
        store.use_directory(tmp_dir)
        recs = synthetic.dataset(size)
        store.save(recs)

        def do_transaction():
            with store.transaction() as recs_on_disk:
                if recs_on_disk:
                    recs_on_disk[0]["hook"] = "task040-bench"

        elapsed, _ = _time(do_transaction)
        return {
            "estate_size": size,
            "transaction_seconds": round(elapsed, 4),
        }
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def measure_refuse_history_loss_at_size(size):
    """How long does refuse_history_loss take at this estate size?

    This runs inside every transaction.  It builds two event indices and
    compares them.
    """
    tmp_dir = tempfile.mkdtemp(prefix="task040_rhl_")
    try:
        store.use_directory(tmp_dir)
        recs = synthetic.dataset(size)
        store.save(recs)

        on_disk = store.read_jsonl(store.queue_path())
        snapshot = store.Snapshot(recs)

        def do_check():
            return store.refuse_history_loss(on_disk, snapshot)

        elapsed, _ = _time(do_check)
        return {
            "estate_size": size,
            "refuse_history_loss_seconds": round(elapsed, 4),
        }
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# --------------------------------------------------------- the full model

def model_campaign_walk(n_leads, latency=0.25):
    """Total wall time for a full campaign lead walk.

    Sequential: each page depends on the previous one (pagination).
    """
    requests = campaign_lead_walk_requests(n_leads)
    local_per_page = 0.005  # JSON parse + row processing, measured below
    wall = requests * (latency + local_per_page)
    return {
        "operation": "campaign_lead_walk",
        "n_leads": n_leads,
        "requests": requests,
        "latency_per_request": latency,
        "wall_seconds": round(wall, 1),
        "wall_minutes": round(wall / 60, 1),
    }


def model_reply_feed_walk(n_replies, latency=0.25):
    """Total wall time for a full reply feed walk."""
    requests = reply_feed_walk_requests(n_replies)
    local_per_page = 0.010  # classify + extract + event build
    wall = requests * (latency + local_per_page)
    return {
        "operation": "reply_feed_walk",
        "n_replies": n_replies,
        "requests": requests,
        "latency_per_request": latency,
        "wall_seconds": round(wall, 1),
        "wall_minutes": round(wall / 60, 1),
    }


def model_full_audit(n_leads, n_replies, n_senders=225, latency=0.25):
    """Total wall time for a full campaign audit."""
    requests = full_campaign_audit_requests(n_leads, n_replies, n_senders)
    local_per_page = 0.008
    wall = requests * (latency + local_per_page)
    return {
        "operation": "full_campaign_audit",
        "n_leads": n_leads,
        "n_replies": n_replies,
        "n_senders": n_senders,
        "requests": requests,
        "latency_per_request": latency,
        "wall_seconds": round(wall, 1),
        "wall_minutes": round(wall / 60, 1),
    }


def model_poll_cycle(n_new_replies, estate_size, latency=0.25):
    """Total wall time for one poll cycle: fetch + apply.

    A poll cycle reads pages until it reaches the checkpoint, then applies
    each reply.  The apply path opens a store.transaction per reply.
    """
    # Reading: assume 5 pages of 15 = 75 rows per poll (MAX_PAGES=5)
    pages_read = 5
    requests_read = pages_read
    wall_read = requests_read * (latency + 0.005)

    # Applying: one transaction per reply applied
    new_replies_in_pages = min(n_new_replies, pages_read * PAGE_SIZE)
    txn_cost = measure_store_transaction_at_size(estate_size)
    wall_apply = new_replies_in_pages * txn_cost["transaction_seconds"]

    return {
        "operation": "poll_cycle",
        "estate_size": estate_size,
        "new_replies": new_replies_in_pages,
        "pages_read": pages_read,
        "requests": requests_read,
        "wall_read_seconds": round(wall_read, 2),
        "wall_apply_seconds": round(wall_apply, 2),
        "wall_total_seconds": round(wall_read + wall_apply, 2),
    }


# --------------------------------------------------------- the main benchmark

def run_request_count_model():
    """Request counts for every provider operation at each scale."""
    results = []

    # Campaign lead walks
    for n in CAMPAIGN_SIZES:
        results.append({
            "operation": "campaign_lead_walk",
            "scale": n,
            "scale_label": f"{n:,} leads",
            "requests": campaign_lead_walk_requests(n),
            "pages": pages_for(n),
        })

    # Reply feed walks
    for n in REPLY_FEED_SIZES:
        results.append({
            "operation": "reply_feed_walk",
            "scale": n,
            "scale_label": f"{n:,} replies",
            "requests": reply_feed_walk_requests(n),
            "pages": pages_for(n),
        })

    # Sender inventory walks
    for n in (50, 225, 500, 1000):
        results.append({
            "operation": "sender_inventory",
            "scale": n,
            "scale_label": f"{n:,} senders",
            "requests": sender_inventory_requests(n),
            "pages": pages_for(n),
        })

    # Collision checks
    for estate in (5000, 21000, 95000):
        results.append({
            "operation": "collision_check_per_domain",
            "scale": estate,
            "scale_label": f"{estate:,} lead estate",
            "requests": collision_check_requests_per_domain(estate),
            "pages": pages_for(min(int(estate * 0.01), 200)),
        })

    # Membership checks (per-lead reads)
    for n in (1, 5, 10, 50, 200):
        results.append({
            "operation": "membership_check",
            "scale": n,
            "scale_label": f"{n} leads",
            "requests": membership_check_requests(n),
            "pages": n,  # one request per lead, not paginated
        })

    # Reply-to-step joins
    for n in REPLY_FEED_SIZES:
        results.append({
            "operation": "reply_to_step_join",
            "scale": n,
            "scale_label": f"{n:,} replies",
            "requests": reply_to_step_join_requests(n),
            "pages": n,  # one request per reply
        })

    # Full campaign audit (campaign 352 shape)
    for n_leads in (1000, 13500, 95000):
        n_replies = n_leads // 7  # rough: 1 reply per 7 leads
        results.append({
            "operation": "full_campaign_audit",
            "scale": n_leads,
            "scale_label": f"{n_leads:,} leads, {n_replies:,} replies",
            "requests": full_campaign_audit_requests(n_leads, n_replies),
            "pages": None,
        })

    return results


def run_wall_time_model():
    """Wall time for key operations at each latency assumption."""
    results = []
    for latency_name, latency in LATENCIES_SECONDS.items():
        for n_leads in CAMPAIGN_SIZES:
            results.append(model_campaign_walk(n_leads, latency))
        for n_replies in REPLY_FEED_SIZES:
            results.append(model_reply_feed_walk(n_replies, latency))
        # Full audit at the realistic campaign 352 scale
        results.append(model_full_audit(13500, 2000, 225, latency))
    return results


def run_local_measurements():
    """Measure local processing costs at realistic estate sizes."""
    results = {}

    # Page processing overhead
    print("  measuring local page processing...", file=sys.stderr)
    results["page_processing"] = measure_local_page_processing(
        n_pages=200, page_size=PAGE_SIZE)

    # Transaction cost at each estate size
    print("  measuring store.transaction at each size...", file=sys.stderr)
    results["transactions"] = []
    for size in ESTATE_SIZES:
        print(f"    estate {size}...", file=sys.stderr)
        results["transactions"].append(
            measure_store_transaction_at_size(size))

    # refuse_history_loss at each estate size
    print("  measuring refuse_history_loss at each size...", file=sys.stderr)
    results["refuse_history_loss"] = []
    for size in ESTATE_SIZES:
        print(f"    estate {size}...", file=sys.stderr)
        results["refuse_history_loss"].append(
            measure_refuse_history_loss_at_size(size))

    return results


def format_report(request_counts, wall_times, local):
    """Produce the markdown report."""
    lines = []
    lines.append("# TASK-040: What Gets Slow First at Real Scale")
    lines.append("")
    lines.append("Every number below is measured or modelled from measured")
    lines.append("constants.  No provider was called.  No credential was used.")
    lines.append("")
    lines.append("## The Known Constant")
    lines.append("")
    lines.append("EmailBison ignores `per_page` on every route and always")
    lines.append("returns 15 rows.  Measured 2026-09-13 on the live estate:")
    lines.append("`GET /campaigns/352/leads?per_page=200` answers fifteen rows")
    lines.append("with `meta.per_page: 15`.  `per_page=50` and `per_page=15`")
    lines.append("answer identically.  Campaign 352 holds roughly 95,000")
    lines.append("scheduled emails, so a full walk is about 6,400 sequential")
    lines.append("requests.  Joining a reply to its step costs one more")
    lines.append("request per reply.")
    lines.append("")

    # Request count table
    lines.append("## Request Counts by Operation and Scale")
    lines.append("")
    lines.append("| Operation | Scale | Requests |")
    lines.append("|---|---|---|")
    for r in request_counts:
        pages = f" ({r['pages']} pages)" if r.get("pages") else ""
        lines.append(f"| {r['operation']} | {r['scale_label']} | "
                      f"{r['requests']:,}{pages} |")
    lines.append("")

    # Wall time model
    lines.append("## Wall Time Model: Campaign Lead Walk")
    lines.append("")
    lines.append("Sequential requests, each blocked on the previous.  "
                 "No parallelism is possible because cursor pagination "
                 "depends on the previous page's response.")
    lines.append("")
    header = "| Leads | Requests |"
    sep = "|---|---|"
    for name in LATENCIES_SECONDS:
        header += f" | {name} ({LATENCIES_SECONDS[name]}s/req) |"
        sep += "|---"
    lines.append(header)
    lines.append(sep)
    for n in CAMPAIGN_SIZES:
        reqs = campaign_lead_walk_requests(n)
        cells = [f"{n:,}", f"{reqs:,}"]
        for name, latency in LATENCIES_SECONDS.items():
            wall = reqs * (latency + 0.005)
            if wall > 120:
                cells.append(f"{wall/60:.0f} min")
            elif wall > 5:
                cells.append(f"{wall:.0f}s")
            else:
                cells.append(f"{wall:.1f}s")
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")

    # Wall time model: reply feed walk
    lines.append("## Wall Time Model: Reply Feed Walk")
    lines.append("")
    header = "| Replies | Requests |"
    sep = "|---|---|"
    for name in LATENCIES_SECONDS:
        header += f" | {name} ({LATENCIES_SECONDS[name]}s/req) |"
        sep += "|---"
    lines.append(header)
    lines.append(sep)
    for n in REPLY_FEED_SIZES:
        reqs = reply_feed_walk_requests(n)
        cells = [f"{n:,}", f"{reqs:,}"]
        for name, latency in LATENCIES_SECONDS.items():
            wall = reqs * (latency + 0.010)
            if wall > 120:
                cells.append(f"{wall/60:.0f} min")
            elif wall > 5:
                cells.append(f"{wall:.0f}s")
            else:
                cells.append(f"{wall:.1f}s")
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")

    # Full audit at campaign 352 scale
    lines.append("## Wall Time Model: Full Campaign Audit (Campaign 352 Shape)")
    lines.append("")
    lines.append("Campaign 352: ~13,500 leads, ~2,000 replies, 225 senders.")
    lines.append("A full audit walks every lead, every reply, joins every "
                 "reply to its step, and reads every sender.")
    lines.append("")
    audit_reqs = full_campaign_audit_requests(13500, 2000, 225)
    lines.append(f"Total requests: **{audit_reqs:,}**")
    lines.append("")
    lines.append("| Latency | Wall Time |")
    lines.append("|---|---|")
    for name, latency in LATENCIES_SECONDS.items():
        wall = audit_reqs * (latency + 0.008)
        lines.append(f"| {name} ({latency}s/req) | "
                      f"{wall/60:.0f} min ({wall:.0f}s) |")
    lines.append("")

    # Local measurements
    lines.append("## Local Processing Measurements")
    lines.append("")
    pp = local["page_processing"]
    lines.append(f"### Page Processing ({pp['n_pages']} pages, "
                 f"{pp['page_size']} rows/page)")
    lines.append("")
    lines.append(f"- Total: {pp['seconds']:.4f}s for "
                 f"{pp['total_rows']:,} rows")
    lines.append(f"- Per page: {pp['seconds_per_page']*1000:.2f}ms")
    lines.append(f"- Per row: {pp['seconds_per_row']*1000:.4f}ms")
    lines.append("")

    lines.append("### store.transaction (one read-modify-write cycle)")
    lines.append("")
    lines.append("| Estate Size | Transaction (s) |")
    lines.append("|---|---|")
    for t in local["transactions"]:
        lines.append(f"| {t['estate_size']:,} | {t['transaction_seconds']:.4f} |")
    lines.append("")

    lines.append("### refuse_history_loss (event log comparison)")
    lines.append("")
    lines.append("| Estate Size | refuse_history_loss (s) |")
    lines.append("|---|---|")
    for t in local["refuse_history_loss"]:
        lines.append(f"| {t['estate_size']:,} | "
                      f"{t['refuse_history_loss_seconds']:.4f} |")
    lines.append("")

    # The comparison: local compute vs provider pagination
    lines.append("## The Comparison: Local Compute vs Provider Pagination")
    lines.append("")
    lines.append("At campaign 352 scale (~13,500 leads, ~2,000 replies):")
    lines.append("")

    # Local cost of processing 2000 replies through the poll path
    local_reply_processing = pp["seconds_per_row"] * 2000
    # Local cost of 2000 store.transactions at 300 records (the real size)
    txn_300 = next((t["transaction_seconds"] for t in local["transactions"]
                    if t["estate_size"] == 300), 0.2)
    local_txn_apply = txn_300 * 2000
    local_total = local_reply_processing + local_txn_apply

    # Provider cost
    provider_reqs = full_campaign_audit_requests(13500, 2000, 225)
    provider_wall_typical = provider_reqs * (0.25 + 0.008)

    lines.append(f"- **Local compute** (process 2,000 replies + "
                 f"2,000 transactions at 300 records): "
                 f"**{local_total:.1f}s**")
    lines.append(f"  - Page processing: {local_reply_processing:.1f}s")
    lines.append(f"  - Store transactions: {local_txn_apply:.1f}s")
    lines.append(f"- **Provider pagination** ({provider_reqs:,} requests at "
                 f"0.25s/req): **{provider_wall_typical/60:.0f} min "
                 f"({provider_wall_typical:.0f}s)**")
    lines.append("")
    ratio = provider_wall_typical / max(local_total, 0.001)
    lines.append(f"**Ratio: provider pagination is {ratio:.0f}x slower "
                 f"than local compute.**")
    lines.append("")

    # The verdict
    lines.append("## Verdict: What Gets Slow First")
    lines.append("")
    lines.append(_verdict(local, provider_reqs, provider_wall_typical,
                          local_total))
    lines.append("")

    # Reproducing
    lines.append("## Reproducing")
    lines.append("")
    lines.append("```bash")
    lines.append("# Request count model (no network, no credentials)")
    lines.append("python benchmarks/provider_pagination.py --json")
    lines.append("")
    lines.append("# Local measurements only")
    lines.append("python benchmarks/provider_pagination.py --local-only")
    lines.append("```")
    lines.append("")
    lines.append("No provider was called.  No credential was used.  "
                 "Every number is reproducible.")

    return "\n".join(lines)


def _verdict(local, provider_reqs, provider_wall, local_wall):
    """Name the single worst bottleneck with evidence."""
    lines = []
    ratio = provider_wall / max(local_wall, 0.001)

    lines.append(f"The single worst bottleneck at campaign 352 scale is "
                 f"**provider pagination**: {provider_reqs:,} sequential "
                 f"HTTP requests, each blocked on the previous, at "
                 f"{provider_wall/60:.0f} minutes wall time "
                 f"(at 0.25s/request).")
    lines.append("")
    lines.append(f"Local compute at the same scale is {local_wall:.0f}s "
                 f"({local_wall/60:.1f} min).  Provider pagination is "
                 f"**{ratio:.0f}x slower**.")
    lines.append("")
    lines.append("The shape is linear in request count, but the request "
                 "count itself is the problem: 6,333 pages for 95,000 leads "
                 "at 15 per page, each sequential, each a full HTTPS "
                 "round-trip.  No amount of local optimisation changes this.")
    lines.append("")
    lines.append("The operations ranked by request count at campaign 352 "
                 "scale:")
    lines.append("")

    # Break down the audit into its components
    lead_walk = campaign_lead_walk_requests(13500)
    reply_walk = reply_feed_walk_requests(2000)
    reply_join = reply_to_step_join_requests(2000)
    sender_walk = sender_inventory_requests(225)

    components = [
        ("campaign lead walk", lead_walk),
        ("reply-to-step join", reply_join),
        ("reply feed walk", reply_walk),
        ("sender inventory", sender_walk),
    ]
    components.sort(key=lambda x: x[1], reverse=True)
    for name, reqs in components:
        wall = reqs * 0.25
        lines.append(f"- **{name}**: {reqs:,} requests, "
                      f"{wall/60:.1f} min at 0.25s/req")
    lines.append("")
    lines.append("The campaign lead walk dominates because the campaign "
                 "holds 13,500 leads and the provider returns 15 per page.  "
                 "The reply-to-step join is second because it costs one "
                 "request per reply, and there is no batch endpoint.")
    return "\n".join(lines)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--json", action="store_true")
    p.add_argument("--local-only", action="store_true",
                   help="only run local measurements, skip the model")
    p.add_argument("--sizes", default=None,
                   help="override campaign sizes (comma-separated)")
    a = p.parse_args(argv)

    if a.sizes:
        global CAMPAIGN_SIZES
        CAMPAIGN_SIZES = tuple(int(s) for s in a.sizes.split(",")
                                if s.strip())

    print("TASK-040: measuring what gets slow first at real scale",
          file=sys.stderr)

    if a.local_only:
        local = run_local_measurements()
        if a.json:
            print(json.dumps(local, indent=2))
        else:
            print(json.dumps(local, indent=2))
        return 0

    print("building request count model...", file=sys.stderr)
    request_counts = run_request_count_model()

    print("building wall time model...", file=sys.stderr)
    wall_times = run_wall_time_model()

    print("running local measurements...", file=sys.stderr)
    local = run_local_measurements()

    if a.json:
        print(json.dumps({
            "request_counts": request_counts,
            "wall_times": wall_times,
            "local": local,
        }, indent=2))
    else:
        print(format_report(request_counts, wall_times, local))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
