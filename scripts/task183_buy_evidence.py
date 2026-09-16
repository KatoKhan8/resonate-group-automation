#!/usr/bin/env python3
"""TASK-183: Buy evidence for 25 records and measure verdict movement.

The question: how many records in `review` with no evidence change verdict
when Grok (via xAI Responses API with web_search) provides sourced facts?

Selection: all 17 records in `review` with zero evidence, plus 8 records in
`review` with exactly 1 evidence row (thinnest evidence), prioritised by
highest ICP score (closest to qualifying, most likely to tip with evidence).

Usage:
    py -3 scripts/task183_buy_evidence.py
    py -3 scripts/task183_buy_evidence.py --dry-run    # select and show, no API calls
"""
import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.providers import load_env, key, MissingKey, ProviderError
from src.providers import xai as xai_adapter
from src import evidence as ev, store, icp, segments, qualify

load_env()

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNAPSHOT = os.path.join(ROOT, "work", "queue.snapshot.jsonl")
WORKING = os.path.join(ROOT, "work", "task183_working.jsonl")
RESULTS = os.path.join(ROOT, "scripts", "task183_results.json")
REPORT = os.path.join(ROOT, "docs", "BOUGHT-EVIDENCE-2026-09-16.md")

BUDGET_USD = 5.00
HARD_STOP_USD = 8.00

RESEARCH_PROMPT = """Research {domain}{company_hint}. Return JSON:
{{"name":"","industry":"","description":"","specialties":[],"employees_estimate":"","founded":"","offices":[],"location":"","sources":{{"field":"url"}}}}
Only include facts with verifiable source URLs. Return ONLY JSON."""

# Fields that map onto company_facts keys the ICP model reads
FACT_FIELDS = (
    "name", "industry", "description", "specialties", "notable",
    "recent_developments", "employees_estimate", "founded", "offices",
    "revenue", "services", "location",
)

# Fields that map onto ICP dimensions through prose matching
PROSE_FIELDS = ("description", "specialties", "services", "notable",
                "recent_developments")


def hash_id(record_id):
    """Hash a record identifier for safe commit."""
    return hashlib.sha256(record_id.encode()).hexdigest()[:12]


def hash_domain(domain):
    return hashlib.sha256(domain.encode()).hexdigest()[:12]


def hash_value(value):
    """Hash a value that might identify a prospect (URLs to their site, etc)."""
    if not value:
        return None
    return hashlib.sha256(str(value).encode()).hexdigest()[:16]


def is_third_party_url(url, domain):
    """Is this URL from a third party (not the company's own site)?"""
    if not url or not domain:
        return True
    return domain not in url


def _task169_sort_key(rec):
    """TASK-169 enrichment ordering: headcount_signal DESC, employees DESC,
    research_outcome=HTTP_SUCCESS first.

    This is the ordering that TASK-169 measured as predicting campaign-ready
    survival: 10+ headcount_signal -> 29.2%, 5-9 -> 16.3%, 1-4 -> 7.3%,
    0 -> 0.0%. The task says to use this ordering if it applies, and it does.
    """
    facts = rec.get("company_facts") or {}
    hs = facts.get("headcount_signal") or 0
    emp = facts.get("employees") or 0
    ro = facts.get("research_outcome") or ""
    return (-hs if isinstance(hs, (int, float)) else 0,
            -emp if isinstance(emp, (int, float)) else 0,
            0 if ro == "HTTP_SUCCESS" else 1)


def _count_review_records():
    """Count total records in `review` status from the snapshot."""
    count = 0
    with open(SNAPSHOT, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            qual = rec.get("qualification") or {}
            verdict = qual.get("verdict") or {}
            if verdict.get("icp_status") == "review":
                count += 1
    return count


def select_records(n=25):
    """Pick records from the snapshot: review with no/ minimal evidence.

    Strategy: all records in `review` with zero evidence first, then fill
    remaining slots from records with exactly 1 evidence row. Within each
    group, ordered by TASK-169's enrichment ordering (headcount_signal DESC,
    employees DESC, research_outcome=HTTP_SUCCESS first) - the ordering that
    predicts campaign-ready survival.
    """
    review_zero = []
    review_thin = []

    with open(SNAPSHOT, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            qual = rec.get("qualification") or {}
            verdict = qual.get("verdict") or {}
            status = verdict.get("icp_status", "")
            research = rec.get("research") or []

            if status != "review":
                continue

            if len(research) == 0:
                review_zero.append(rec)
            elif len(research) == 1:
                review_thin.append(rec)

    # TASK-169 ordering: headcount_signal DESC, employees DESC, HTTP_SUCCESS first
    review_zero.sort(key=_task169_sort_key)
    review_thin.sort(key=_task169_sort_key)

    selected = review_zero[:]
    remaining = n - len(selected)
    if remaining > 0:
        selected.extend(review_thin[:remaining])

    return selected[:n]


def call_grok_responses(domain, company_name=None, max_retries=2):
    """Call Grok via the adapter (TASK-182: Responses API with web_search).

    Uses src.providers.xai.respond() - the adapter owns auth, retry,
    endpoint selection and response trimming.  This script never calls
    the endpoint directly.

    Script-level retry wraps the adapter's internal retry: the adapter
    retries once on 5xx/network errors within its 60s timeout.  This
    outer retry handles cases where the adapter's timeout fires and
    raises ProviderError with a timeout message.
    """
    company_hint = f" ({company_name})" if company_name else ""
    prompt = RESEARCH_PROMPT.format(domain=domain, company_hint=company_hint)

    last_error = None
    for attempt in range(max_retries + 1):
        try:
            result = xai_adapter.respond(
                input_messages=[{"role": "user", "content": prompt}],
                model="grok-4.6",
                max_tokens=2048,
                temperature=0.3,
                tools=[{"type": "web_search"}],
            )
            return {
                "content": result.get("content") or "",
                "usage": result.get("usage") or {},
                "search_urls": result.get("search_urls") or [],
                "model": result.get("model"),
            }
        except MissingKey:
            raise
        except ProviderError as e:
            last_error = str(e)
            if "timeout" in last_error.lower() and attempt < max_retries:
                time.sleep(1)
                continue
            return {"error": last_error, "content": "", "usage": {},
                    "search_urls": []}
    return {"error": last_error or "unknown", "content": "", "usage": {},
            "search_urls": []}


def parse_grok_json(content):
    """Parse Grok's JSON response, handling markdown code blocks."""
    if not content:
        return {}
    text = content.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        import re
        match = re.search(r'\{[\s]*\n?[\s]*"', text)
        if match:
            start = match.start()
            depth = 0
            end = start
            for i in range(start, len(text)):
                if text[i] == '{':
                    depth += 1
                elif text[i] == '}':
                    depth -= 1
                    if depth == 0:
                        end = i + 1
                        break
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                pass
        return {"_raw": text[:500], "_parse_error": True}


def _normalize_grok_data(grok_data):
    """Normalize Grok's response to flat format.

    Grok may return either:
      Flat:   {"name": "Linear", "sources": {"name": "https://..."}}
      Nested: {"name": {"value": "Linear", "sources": ["https://..."]}}

    Returns (flat_dict, sources_dict) where sources_dict maps field -> URL.
    """
    sources = grok_data.get("sources") or {}
    flat = {}
    flat_sources = dict(sources)

    for field in FACT_FIELDS:
        raw = grok_data.get(field)
        if raw is None:
            continue
        if isinstance(raw, dict) and "value" in raw:
            flat[field] = raw["value"]
            nested_sources = raw.get("sources") or []
            if isinstance(nested_sources, list) and nested_sources:
                flat_sources[field] = nested_sources[0]
            elif isinstance(nested_sources, str):
                flat_sources[field] = nested_sources
        else:
            flat[field] = raw

    return flat, flat_sources


def grok_to_company_facts(rec, grok_data):
    """Merge Grok's sourced facts into company_facts.

    Only fields with a source URL are written. A fact without provenance
    cannot pass the claims gate, so it is worth nothing.
    """
    flat, sources = _normalize_grok_data(grok_data)
    facts = rec.get("company_facts") or {}
    new_facts = {}

    for field in FACT_FIELDS:
        value = flat.get(field)
        if not value:
            continue
        source_url = sources.get(field)
        if not source_url:
            continue

        existing = facts.get(field)
        if field in ("specialties", "notable", "recent_developments", "offices",
                      "services"):
            if not isinstance(value, list):
                value = [value]
            existing_list = existing if isinstance(existing, list) else []
            merged = list(existing_list)
            for item in value:
                if not any(str(item).lower() == str(e).lower()
                           for e in existing_list):
                    merged.append(item)
            if len(merged) > len(existing_list):
                new_facts[field] = merged
        elif field == "employees_estimate":
            parsed = _parse_employee_count(value)
            if parsed and not facts.get("employees"):
                new_facts["employees"] = parsed
        elif field == "founded":
            parsed = _parse_year(value)
            if parsed and not facts.get("founded"):
                new_facts["founded"] = parsed
        else:
            if not existing:
                new_facts[field] = value

    return new_facts


def grok_to_research_entries(rec, grok_data, retrieved_at):
    """Convert Grok's sourced facts into research entries.

    Each entry carries provenance (source_url, retrieved_at, evidence_id)
    so it passes the same gates as free-path evidence.
    """
    flat, sources = _normalize_grok_data(grok_data)
    entries = []
    domain = rec.get("domain", "")
    record_id = rec.get("id", "")

    for field in FACT_FIELDS:
        value = flat.get(field)
        if not value:
            continue
        source_url = sources.get(field)
        if not source_url:
            continue

        if isinstance(value, list):
            for item in value:
                fact_text = f"{field}: {item}"
                entry = ev.make(
                    fact=fact_text,
                    source_url=source_url,
                    source_type="web_search",
                    provider="grok",
                    record_id=record_id,
                    retrieved_at=retrieved_at,
                    confidence="medium",
                )
                entries.append(entry)
        else:
            fact_text = f"{field}: {value}"
            entry = ev.make(
                fact=fact_text,
                source_url=source_url,
                source_type="web_search",
                provider="grok",
                record_id=record_id,
                retrieved_at=retrieved_at,
                confidence="medium",
            )
            entries.append(entry)

    return entries


def _parse_employee_count(value):
    """Extract an integer employee count from various formats."""
    if isinstance(value, int):
        return value
    text = str(value).lower().strip()
    import re
    match = re.search(r'(\d[\d,]*)', text)
    if match:
        return int(match.group(1).replace(",", ""))
    ranges = {"1-10": 5, "11-50": 25, "51-200": 100, "201-500": 350,
              "501-1000": 750, "1001-5000": 2500}
    for pattern, estimate in ranges.items():
        if pattern in text:
            return estimate
    return None


def _parse_year(value):
    """Extract a year integer."""
    if isinstance(value, int) and 1800 <= value <= 2026:
        return value
    import re
    match = re.search(r'(1[89]\d{2}|20[0-2]\d)', str(value))
    if match:
        return int(match.group(1))
    return None


def requalify_record(rec, config=None):
    """Re-run qualification on a record after evidence was added.

    Uses the real qualify.company() entry point, which is what production
    calls. Returns the new verdict.
    """
    result = qualify.company(rec, config, store_result=True)
    return result.get("verdict", {})


def run_claims_gate(rec):
    """Run the claims gate against the record's new facts.

    Returns whether the claims gate would accept or refuse copy based on
    the evidence now held.
    """
    from src import claims
    support = claims.support_text(rec)
    research = rec.get("research") or []
    return {
        "support_length": len(support),
        "evidence_count": len(research),
        "evidence_with_source": sum(1 for e in research if e.get("source_url")),
        "quality_distribution": {
            q: sum(1 for e in research if e.get("quality") == q)
            for q in ("strong", "medium", "weak", "unusable")
        },
    }


def _load_previous_results():
    """Load previous results for resume capability."""
    if not os.path.exists(RESULTS):
        return None
    try:
        with open(RESULTS, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def main(argv=None):
    p = argparse.ArgumentParser(prog="task183_buy_evidence")
    p.add_argument("--dry-run", action="store_true",
                   help="select records and show plan, no API calls")
    p.add_argument("--limit", type=int, default=25,
                   help="number of records (hard stop at 25)")
    p.add_argument("--resume", action="store_true",
                   help="skip records already in results file")
    a = p.parse_args(argv)

    n = min(a.limit, 25)
    print(f"{'=' * 70}")
    print(f"TASK-183: Buy evidence for {n} records")
    print(f"Started: {datetime.now(timezone.utc).isoformat()}")
    print(f"Snapshot: {SNAPSHOT}")
    print(f"{'=' * 70}")
    print()

    # --- Selection ---
    selected = select_records(n)
    print(f"Selected {len(selected)} records:")
    zero_ev = sum(1 for r in selected if not (r.get("research") or []))
    thin_ev = len(selected) - zero_ev
    print(f"  {zero_ev} with zero evidence")
    print(f"  {thin_ev} with 1 evidence row")
    print()

    if a.dry_run:
        print("DRY RUN - no API calls. Records that would be processed:")
        for rec in selected:
            rid = rec.get("id", "?")
            domain = rec.get("domain", "?")
            verdict = (rec.get("qualification") or {}).get("verdict") or {}
            print(f"  {hash_id(rid)}  {hash_domain(domain)}  "
                  f"score={verdict.get('icp_score', 0)}  "
                  f"evidence={len(rec.get('research') or [])}")
        return 0

    # --- Check API key ---
    try:
        key("XAI_API_KEY")
    except MissingKey as e:
        print(f"BLOCKED: {e}")
        print("XAI_API_KEY is not configured in this worktree.")
        print("The script is ready to run once the key is available.")
        return 2

    # --- Resume from previous run ---
    results = []
    total_cost_ticks = 0
    total_cost_usd = 0.0
    movement = {"qualified": 0, "rejected": 0, "still_review": 0,
                "unknown": 0, "confidence_off_low": 0}
    still_unknown_criteria = []
    skip_ids = set()

    if a.resume:
        prev = _load_previous_results()
        if prev:
            results = prev.get("results", [])
            total_cost_usd = prev.get("total_cost_usd", 0.0)
            total_cost_ticks = prev.get("total_cost_ticks", 0)
            prev_movement = prev.get("movement", {})
            for k in movement:
                movement[k] = prev_movement.get(k, 0)
            still_unknown_criteria = prev.get("still_unknown_criteria", [])
            for r in results:
                h = r.get("record_id_hash")
                if h:
                    skip_ids.add(h)
            print(f"Resuming: {len(results)} previous results loaded, "
                  f"${total_cost_usd:.4f} spent so far")
            print(f"Skipping {len(skip_ids)} already-processed records")
            print()

    # --- Process each record ---
    processed_count = len(results)
    for i, rec in enumerate(selected, 1):
        rid = rec.get("id", "?")
        domain = rec.get("domain", "?")
        company = rec.get("company", "")
        h_id = hash_id(rid)
        h_domain = hash_domain(domain)

        if h_id in skip_ids:
            continue

        # Pre-evidence verdict
        old_verdict = (rec.get("qualification") or {}).get("verdict") or {}
        old_status = old_verdict.get("icp_status", "unknown")
        old_score = old_verdict.get("icp_score", 0)
        old_confidence = old_verdict.get("icp_confidence", "low")

        processed_count += 1
        print(f"[{processed_count}/{n}] {h_id} ({h_domain})... ", end="", flush=True)

        # Call Grok through the adapter
        try:
            grok_result = call_grok_responses(domain, company)
        except MissingKey:
            print(f"\nBLOCKED: XAI_API_KEY missing mid-run")
            break

        if grok_result.get("error"):
            print(f"ERROR: {grok_result['error'][:80]}")
            results.append({
                "record_id_hash": h_id, "domain_hash": h_domain,
                "error": grok_result["error"],
            })
            continue

        content = grok_result.get("content", "")
        grok_data = parse_grok_json(content)

        if grok_data.get("_parse_error"):
            print(f"PARSE ERROR")
            results.append({
                "record_id_hash": h_id, "domain_hash": h_domain,
                "parse_error": True,
                "raw": grok_data.get("_raw", "")[:200],
            })
            continue

        # Cost tracking - use the adapter's converter (10B ticks = $1)
        usage = grok_result.get("usage", {})
        cost_ticks = usage.get("cost_in_usd_ticks", 0) or 0
        cost_usd = xai_adapter.ticks_to_usd(cost_ticks) or 0
        total_cost_ticks += cost_ticks
        total_cost_usd += cost_usd

        # Check budget
        if total_cost_usd > HARD_STOP_USD:
            print(f"\nBUDGET HARD STOP: ${total_cost_usd:.2f} > ${HARD_STOP_USD}")
            break

        # Write evidence onto the record
        retrieved_at = store.now()
        new_facts = grok_to_company_facts(rec, grok_data)
        new_research = grok_to_research_entries(rec, grok_data, retrieved_at)

        # Merge company_facts
        facts = rec.get("company_facts") or {}
        facts.update(new_facts)
        rec["company_facts"] = facts

        # Append research entries
        rec.setdefault("research", []).extend(new_research)

        search_urls = grok_result.get("search_urls", [])

        print(f"${cost_usd:.4f}, facts={len(new_facts)}, "
              f"research={len(new_research)}, sources={len(search_urls)}")

        # Re-qualify
        new_verdict = requalify_record(rec)
        new_status = new_verdict.get("icp_status", "unknown")
        new_score = new_verdict.get("icp_score", 0)
        new_confidence = new_verdict.get("icp_confidence", "low")
        new_missing = new_verdict.get("missing_evidence", [])

        # Track movement
        if new_status == icp.QUALIFIED:
            movement["qualified"] += 1
        elif new_status == icp.REJECTED:
            movement["rejected"] += 1
        elif new_status == icp.REVIEW:
            movement["still_review"] += 1
            still_unknown_criteria.append({
                "record_id_hash": h_id,
                "missing": new_missing[:3],
            })
        else:
            movement["unknown"] += 1

        if new_confidence != "low":
            movement["confidence_off_low"] += 1

        # Claims gate for newly qualified
        claims_result = None
        if new_status == icp.QUALIFIED:
            claims_result = run_claims_gate(rec)

        results.append({
            "record_id_hash": h_id,
            "domain_hash": h_domain,
            "company_hash": hash_value(company),
            "old_status": old_status,
            "old_score": old_score,
            "old_confidence": old_confidence,
            "new_status": new_status,
            "new_score": new_score,
            "new_confidence": new_confidence,
            "new_missing": new_missing[:5],
            "facts_added": len(new_facts),
            "research_added": len(new_research),
            "cost_usd": cost_usd,
            "cost_ticks": cost_ticks,
            "search_urls_count": len(search_urls),
            "claims_gate": claims_result,
            "usage": usage,
        })

        # Save incrementally
        _save_results(results, movement, total_cost_ticks, total_cost_usd,
                      still_unknown_criteria)

        if total_cost_usd > BUDGET_USD:
            print(f"\nBUDGET WARNING: ${total_cost_usd:.2f} > ${BUDGET_USD:.2f}")

    # --- Final report ---
    print()
    print(f"{'=' * 70}")
    print("SUMMARY")
    print(f"{'=' * 70}")
    print()
    successful = [r for r in results if "new_status" in r]
    failed = [r for r in results if "error" in r or "parse_error" in r]
    print(f"Records processed: {len(successful)}")
    print(f"Records failed: {len(failed)}")
    print(f"Total cost: ${total_cost_usd:.4f} ({total_cost_ticks} ticks)")
    if successful:
        print(f"Average cost per record: ${total_cost_usd / len(successful):.4f}")
    print()
    print("Verdict movement:")
    print(f"  review -> qualified:  {movement['qualified']}")
    print(f"  review -> rejected:   {movement['rejected']}")
    print(f"  review -> still review: {movement['still_review']}")
    print(f"  review -> unknown:    {movement['unknown']}")
    print(f"  confidence off low:   {movement['confidence_off_low']}")
    print()

    if still_unknown_criteria:
        print("Still-UNKNOWN criteria (sample):")
        for entry in still_unknown_criteria[:5]:
            print(f"  {entry['record_id_hash']}: {entry['missing']}")
        print()

    review_total = _count_review_records()
    verdicts_changed = movement["qualified"] + movement["rejected"]
    if verdicts_changed > 0:
        cost_per_verdict = total_cost_usd / verdicts_changed
        print(f"Cost per verdict change: ${cost_per_verdict:.4f}")
        remaining = review_total - len(successful)
        projection = cost_per_verdict * remaining
        print(f"Projection to {review_total} review records: ${projection:.2f}")
    else:
        cost_per_verdict = None
        print("Cost per verdict change: cannot compute (no verdict changes)")
        print(f"Projection: cannot compute (no verdict changes in {len(successful)} records)")
    print()

    qualified_results = [r for r in successful if r["new_status"] == "qualified"]
    if qualified_results:
        print("Claims gate on newly qualified:")
        for r in qualified_results:
            cg = r.get("claims_gate") or {}
            print(f"  {r['record_id_hash']}: evidence={cg.get('evidence_count')}, "
                  f"with_source={cg.get('evidence_with_source')}, "
                  f"quality={cg.get('quality_distribution')}")
    print()

    print(f"Results saved to: {RESULTS}")
    return 0


def _save_results(results, movement, total_cost_ticks, total_cost_usd,
                  still_unknown_criteria):
    """Save results incrementally so a timeout loses nothing."""
    successful = [r for r in results if "new_status" in r]
    failed = [r for r in results if "error" in r or "parse_error" in r]
    verdicts = movement["qualified"] + movement["rejected"]
    cost_per_verdict = (total_cost_usd / verdicts) if verdicts > 0 else None
    review_total = _count_review_records()
    remaining = review_total - len(successful)
    projection = (cost_per_verdict * remaining) if cost_per_verdict else None

    with open(RESULTS, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "records_processed": len(successful),
            "records_failed": len(failed),
            "total_cost_ticks": total_cost_ticks,
            "total_cost_usd": total_cost_usd,
            "movement": movement,
            "still_unknown_criteria": still_unknown_criteria,
            "cost_per_verdict": cost_per_verdict,
            "review_total": review_total,
            "projection_to_review_total": projection,
            "results": results,
        }, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    raise SystemExit(main())
