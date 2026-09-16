#!/usr/bin/env python3
"""TASK-166: Grok vs free research measurement.

Pick 10 domains with company_facts already populated, ask Grok the company
research question with web_search enabled via the Responses API, and compare
against the existing evidence from the free path (webfetch/Apify).

Results are saved incrementally after each domain so a timeout does not lose
everything.

Usage:
    py -3 scripts/task166_grok_measurement.py
"""
import json
import os
import sys
import hashlib
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.providers import load_env, key, request, ok, ProviderError

load_env()

SNAPSHOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "work", "queue.snapshot.jsonl")
RESPONSES_URL = "https://api.x.ai/v1/responses"
RESULTS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "scripts", "task166_results.json")

RESEARCH_PROMPT = """Research the company at domain "{domain}"{company_hint}.

Return a JSON object with these fields (omit any you cannot verify):
{{
  "name": "company name",
  "industry": "what industry they are in",
  "description": "one sentence what the company does",
  "specialties": ["list", "of", "specialties", "or", "services"],
  "notable": ["notable clients, projects, or achievements"],
  "recent_developments": ["recent news, launches, hiring, funding, partnerships"],
  "employees_estimate": "employee count or range if found",
  "founded": "year founded if found",
  "offices": ["locations"]
}}

For each fact you assert, include the source URL in a separate field:
{{
  "sources": {{
    "field_name": "https://source-url.com"
  }}
}}

Only include facts you can attribute to a source. Do not infer or guess.
Return ONLY the JSON object, no other text."""


def pick_domains(n=10):
    """Pick n domains with meaningful company_facts and research rows."""
    candidates = []
    with open(SNAPSHOT, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            facts = rec.get("company_facts") or {}
            research = rec.get("research") or []
            meaningful_keys = {"industry", "employees", "specialties", "notable"}
            has_meaningful = any(facts.get(k) for k in meaningful_keys)
            if has_meaningful and research:
                candidates.append(rec)

    # Diverse pick: up to 2 per industry
    by_industry = {}
    for rec in candidates:
        ind = (rec.get("company_facts") or {}).get("industry", "")
        by_industry.setdefault(ind, []).append(rec)

    result = []
    for ind, recs in by_industry.items():
        result.extend(recs[:2])
    return result[:n]


def hash_domain(domain):
    return hashlib.sha256(domain.encode()).hexdigest()[:12]


def call_grok_responses(domain, company_name=None, max_retries=2):
    """Call Grok via the Responses API with web_search enabled."""
    company_hint = f" (company name: {company_name})" if company_name else ""
    prompt = RESEARCH_PROMPT.format(domain=domain, company_hint=company_hint)

    api_key = key("XAI_API_KEY")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": "grok-4.6",
        "input": [{"role": "user", "content": prompt}],
        "tools": [{"type": "web_search"}],
        "max_output_tokens": 4096,
        "temperature": 0.3,
    }

    for attempt in range(max_retries + 1):
        try:
            status, data = request("POST", RESPONSES_URL, headers, body, 90)
            if ok(status):
                return _parse_responses(data)
            if 400 <= status < 500 and status != 429:
                return {"error": f"HTTP {status}: {str(data)[:200]}",
                        "content": None, "usage": {}, "search_urls": []}
        except ProviderError as e:
            if attempt >= max_retries:
                return {"error": str(e), "content": None, "usage": {}, "search_urls": []}
        if attempt < max_retries:
            time.sleep(1 * (2 ** attempt))

    return {"error": "max retries exceeded", "content": None, "usage": {}, "search_urls": []}


def _parse_responses(data):
    """Extract content, usage, and search URLs from the Responses API response."""
    output = (data or {}).get("output") or []
    content_parts = []
    search_urls = []

    for item in output:
        item_type = item.get("type")
        if item_type == "message":
            for c in item.get("content") or []:
                if c.get("type") == "output_text":
                    content_parts.append(c.get("text", ""))
        elif item_type == "web_search_call":
            # Extract URLs the search actually visited
            action = item.get("action") or {}
            for src in action.get("sources") or []:
                if src.get("type") == "url":
                    search_urls.append(src.get("url", ""))

    usage = (data or {}).get("usage") or {}
    return {
        "content": "\n".join(content_parts),
        "usage": {
            "prompt_tokens": usage.get("input_tokens"),
            "completion_tokens": usage.get("output_tokens"),
            "total_tokens": usage.get("total_tokens"),
            "cached_tokens": (usage.get("input_tokens_details") or {}).get("cached_tokens"),
            "reasoning_tokens": (usage.get("output_tokens_details") or {}).get("reasoning_tokens"),
            "cost_in_usd_ticks": usage.get("cost_in_usd_ticks"),
            "num_sources_used": usage.get("num_sources_used"),
        },
        "model": (data or {}).get("model"),
        "search_urls": search_urls,
    }


def parse_grok_response(content):
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
            # Find the outermost braces
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


def extract_existing_facts(rec):
    facts = rec.get("company_facts") or {}
    research = rec.get("research") or []
    existing = {"structured": {}, "research": []}
    for k in ("name", "industry", "employees", "specialties", "notable",
              "founded", "offices", "revenue"):
        val = facts.get(k)
        if val not in (None, "", [], {}):
            existing["structured"][k] = val
    for entry in research:
        fact_text = entry.get("fact", "")
        source_url = entry.get("source_url", "")
        quality = entry.get("quality", "")
        if fact_text and quality in ("medium", "strong"):
            existing["research"].append({
                "fact": fact_text[:200],
                "source_url": source_url,
                "quality": quality,
            })
    return existing


def compare_facts(grok_data, existing):
    comparison = {
        "confirmed": [],
        "new_from_grok": [],
        "contradictions": [],
        "unsourced": [],
    }
    sources = grok_data.get("sources", {})
    structured = existing["structured"]

    for field in ("name", "industry", "description", "employees_estimate", "founded"):
        grok_val = grok_data.get(field)
        if not grok_val:
            continue
        source_url = sources.get(field)
        if not source_url:
            comparison["unsourced"].append({"field": field, "value": str(grok_val)[:100]})
            continue
        existing_val = structured.get(field)
        if existing_val:
            grok_str = str(grok_val).lower().strip()
            exist_str = str(existing_val).lower().strip()
            if grok_str == exist_str or grok_str in exist_str or exist_str in grok_str:
                comparison["confirmed"].append({
                    "field": field, "grok_value": grok_val,
                    "existing_value": existing_val, "source": source_url,
                })
            else:
                comparison["contradictions"].append({
                    "field": field, "grok_value": grok_val, "grok_source": source_url,
                    "existing_value": existing_val, "existing_source": "structured (ContactOut/Apify)",
                })
        else:
            comparison["new_from_grok"].append({
                "field": field, "value": grok_val, "source": source_url,
            })

    for field in ("specialties", "notable", "recent_developments", "offices"):
        grok_list = grok_data.get(field) or []
        if not grok_list:
            continue
        source_url = sources.get(field)
        existing_list = structured.get(field) or []
        if isinstance(existing_list, str):
            existing_list = [existing_list]
        for item in grok_list:
            if not source_url:
                comparison["unsourced"].append({"field": field, "value": str(item)[:100]})
                continue
            item_lower = str(item).lower().strip()
            found = False
            for ex in existing_list:
                ex_lower = str(ex).lower().strip()
                if item_lower == ex_lower or item_lower in ex_lower or ex_lower in item_lower:
                    comparison["confirmed"].append({
                        "field": field, "grok_value": item,
                        "existing_value": ex, "source": source_url,
                    })
                    found = True
                    break
            if not found:
                comparison["new_from_grok"].append({
                    "field": field, "value": item, "source": source_url,
                })

    return comparison


def save_results(results, total_counts, total_cost_ticks):
    successful = [r for r in results if "comparison" in r]
    failed = [r for r in results if "error" in r or "parse_error" in r]
    projection_ticks = 0
    projection_usd = 0
    if successful:
        avg_cost = total_cost_ticks / len(successful)
        projection_ticks = avg_cost * 316
        projection_usd = projection_ticks / 1e10

    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "domains_measured": len(successful),
            "domains_failed": len(failed),
            "total_cost_ticks": total_cost_ticks,
            "total_cost_usd": total_cost_ticks / 1e10,
            "counts": total_counts,
            "projection_316_domains": {
                "estimated_ticks": projection_ticks,
                "estimated_usd": projection_usd,
            },
            "results": results,
        }, f, indent=2, ensure_ascii=False)


def main():
    print("=" * 70)
    print("TASK-166: Grok vs Free Research Measurement")
    print(f"Started: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 70)
    print()

    domains = pick_domains(10)
    print(f"Selected {len(domains)} domains for measurement")
    print()

    results = []
    total_cost_ticks = 0
    total_counts = {"confirmed": 0, "new_from_grok": 0, "contradictions": 0, "unsourced": 0}

    for i, rec in enumerate(domains, 1):
        domain = rec["domain"]
        company = rec.get("company", "")
        domain_hash = hash_domain(domain)

        print(f"[{i}/10] {domain_hash}... ", end="", flush=True)

        existing = extract_existing_facts(rec)
        grok_result = call_grok_responses(domain, company)

        if grok_result.get("error"):
            print(f"ERROR: {grok_result['error'][:80]}")
            results.append({
                "domain_hash": domain_hash, "domain": domain,
                "company": company, "error": grok_result["error"],
            })
            save_results(results, total_counts, total_cost_ticks)
            continue

        content = grok_result.get("content", "")
        grok_data = parse_grok_response(content)

        if grok_data.get("_parse_error"):
            print(f"PARSE ERROR")
            results.append({
                "domain_hash": domain_hash, "domain": domain,
                "company": company, "parse_error": True,
                "raw": grok_data.get("_raw", "")[:200],
            })
            save_results(results, total_counts, total_cost_ticks)
            continue

        comparison = compare_facts(grok_data, existing)

        usage = grok_result.get("usage", {})
        cost_ticks = usage.get("cost_in_usd_ticks", 0) or 0
        total_cost_ticks += cost_ticks
        for k in total_counts:
            total_counts[k] += len(comparison[k])

        search_urls = grok_result.get("search_urls", [])
        print(f"cost=${cost_ticks/1e10:.4f}, "
              f"search_urls={len(search_urls)}, "
              f"confirmed={len(comparison['confirmed'])}, "
              f"new={len(comparison['new_from_grok'])}, "
              f"contra={len(comparison['contradictions'])}, "
              f"unsourced={len(comparison['unsourced'])}")

        results.append({
            "domain_hash": domain_hash, "domain": domain, "company": company,
            "existing_structured": existing["structured"],
            "existing_research_count": len(existing["research"]),
            "grok_data": grok_data,
            "search_urls": search_urls,
            "comparison": comparison,
            "usage": usage,
            "cost_ticks": cost_ticks,
            "cost_usd": cost_ticks / 1e10 if cost_ticks else 0,
        })

        # Save incrementally
        save_results(results, total_counts, total_cost_ticks)

    # Final summary
    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print()

    successful = [r for r in results if "comparison" in r]
    failed = [r for r in results if "error" in r or "parse_error" in r]
    print(f"Domains measured: {len(successful)}")
    if failed:
        print(f"Domains failed: {len(failed)}")
    print(f"Total cost: ${total_cost_ticks / 1e10:.4f} USD ({total_cost_ticks} ticks)")
    if successful:
        print(f"Average cost per domain: ${total_cost_ticks / len(successful) / 1e10:.4f} USD")
    print()
    print("Fact counts across all domains:")
    for k, count in total_counts.items():
        print(f"  {k}: {count}")
    print()

    if successful:
        avg_cost = total_cost_ticks / len(successful)
        projection_ticks = avg_cost * 316
        projection_usd = projection_ticks / 1e10
        print(f"Projection to 316 domains:")
        print(f"  Estimated cost: ${projection_usd:.2f} USD ({projection_ticks:.0f} ticks)")
    print()

    all_contradictions = []
    for r in results:
        if "comparison" in r:
            for c in r["comparison"].get("contradictions", []):
                c["domain_hash"] = r["domain_hash"]
                all_contradictions.append(c)

    if all_contradictions:
        print(f"CONTRADICTIONS ({len(all_contradictions)}):")
        for c in all_contradictions:
            print(f"  [{c['domain_hash']}] {c['field']}:")
            print(f"    Grok: {c['grok_value']} (source: {c['grok_source']})")
            print(f"    Existing: {c['existing_value']} (source: {c['existing_source']})")
            print()
    else:
        print("No contradictions found.")
    print()

    print(f"Results saved to: {RESULTS_FILE}")
    return results, total_counts, total_cost_ticks


if __name__ == "__main__":
    main()
