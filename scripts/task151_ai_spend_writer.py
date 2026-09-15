#!/usr/bin/env python3
"""AI spend ledger writer — TASK-151.

Records one row per model call: stage, model, tokens, cost, hashed record id.
No prompt contents. No raw identifiers. No credentials.

This is the instrument, not the optimisation. It appends to a JSONL file
and nothing more. Claude wires it into `llm.ask`; this script does not.

Usage as a library:

    from scripts.task151_ai_spend_writer import record_call, ledger_path

    record_call(
        client="productive",
        stage="draft",
        task="generate.draft",
        record_id="16kagency-com",
        model="anthropic/claude-3.5-sonnet",
        provider="openrouter",
        input_tokens=1842,
        output_tokens=356,
        latency=2.341,
        retry_count=0,
        cost=0.00891,
        cost_source="openrouter_reported",
        success=True,
    )

Usage as a CLI:

    python scripts/task151_ai_spend_writer.py --json < row.jsonl
    python scripts/task151_ai_spend_writer.py --report --day 2026-09-15
"""
import argparse
import datetime
import hashlib
import json
import os
import sys
import tempfile

# ------------------------------------------------------------------ hashing

def hash_record_id(raw_id):
    """SHA-256 of the record id, truncated to 16 hex chars.

    Same pattern as `generate.fingerprint()` and 14 other modules in src/.
    The ledger answers "which stage spent this" without becoming a second
    copy of the estate.
    """
    if not raw_id:
        return None
    return hashlib.sha256(str(raw_id).encode("utf-8")).hexdigest()[:16]


# --------------------------------------------------------- price table

def estimate_cost(input_tokens, output_tokens, price_entry,
                  cached_tokens=None):
    """Compute cost from a price table entry.

    `price_entry` is a dict with `input_per_1m`, `output_per_1m`, and
    optionally `cached_input_per_1m`. Returns USD as a float.

    Returns None if no price entry is available — the caller should use
    OpenRouter's reported cost instead.
    """
    if not price_entry:
        return None
    inp = (input_tokens or 0) * price_entry.get("input_per_1m", 0) / 1_000_000
    out = (output_tokens or 0) * price_entry.get("output_per_1m", 0) / 1_000_000
    cached = 0
    if cached_tokens and "cached_input_per_1m" in price_entry:
        cached = cached_tokens * price_entry["cached_input_per_1m"] / 1_000_000
    return round(inp + out + cached, 8)


# --------------------------------------------------------- ledger path

def ledger_path(env_var="AI_SPEND_LEDGER"):
    """Where the ledger lives. Beside the provider spend ledger.

    Falls back to a temp directory when neither the env var nor `work/`
    is available — tests use this, and a production run without `work/`
    should not silently write to the repository root.
    """
    explicit = os.environ.get(env_var)
    if explicit:
        return explicit
    work = os.path.join(os.path.dirname(os.path.dirname(__file__)), "work")
    if os.path.isdir(work):
        return os.path.join(work, "ai-spend-ledger.jsonl")
    return os.path.join(tempfile.gettempdir(), "ai-spend-ledger.jsonl")


# --------------------------------------------------------- the writer

def record_call(
    *,
    client,
    stage,
    task=None,
    record_id=None,
    model="",
    provider="openrouter",
    prompt_version="v1",
    input_tokens=0,
    output_tokens=0,
    cached_tokens=None,
    latency=0.0,
    retry_count=0,
    cost=None,
    cost_source=None,
    price_table_version=None,
    success=True,
    cache_hit=None,
    at=None,
    path=None,
):
    """Append one model-call row to the AI spend ledger.

    Returns the row dict. Does NOT call a model — the caller provides
    the observed values.

    `cost` is the estimated or reported cost in USD. When None and no
    price table is available, cost is 0 and cost_source is "unknown".

    `record_id` is hashed before writing. The raw value never touches
    the ledger file.
    """
    now = at or datetime.datetime.now(datetime.timezone.utc).replace(
        microsecond=0).isoformat()
    day = now[:10]

    if cost is None:
        cost = 0
        cost_source = cost_source or "unknown"
    elif cost_source is None:
        cost_source = "openrouter_reported"

    if cache_hit is None and cached_tokens is not None:
        cache_hit = cached_tokens > 0

    row = {
        "at": now,
        "day": day,
        "client": client,
        "stage": stage,
        "task": task or stage,
        "record_id": hash_record_id(record_id),
        "model": model,
        "provider": provider,
        "prompt_version": prompt_version,
        "input_tokens": int(input_tokens or 0),
        "output_tokens": int(output_tokens or 0),
        "cached_tokens": int(cached_tokens) if cached_tokens else None,
        "latency": round(float(latency or 0), 3),
        "retry_count": int(retry_count or 0),
        "estimated_cost": float(cost),
        "cost_source": cost_source,
        "price_table_version": price_table_version,
        "success": bool(success),
        "cache_hit": cache_hit,
    }

    dest = path or ledger_path()
    os.makedirs(os.path.dirname(os.path.abspath(dest)), exist_ok=True)
    with open(dest, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


# --------------------------------------------------------- reporting

def load_ledger(path=None):
    """Read every row from the ledger. Returns a list of dicts."""
    dest = path or ledger_path()
    try:
        with open(dest, "r", encoding="utf-8") as fh:
            rows = []
            for line in fh:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
            return rows
    except FileNotFoundError:
        return []


def report(rows=None, day=None, client=None, path=None):
    """Summarise AI spend, optionally filtered by day and/or client.

    Returns a dict suitable for JSON serialisation or printing.
    """
    rows = rows if rows is not None else load_ledger(path)
    filtered = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if day and row.get("day") != day:
            continue
        if client and row.get("client") != client:
            continue
        filtered.append(row)

    by_stage = {}
    by_model = {}
    total_cost = 0.0
    total_calls = 0
    total_input = 0
    total_output = 0
    successes = 0
    failures = 0

    for row in filtered:
        cost = float(row.get("estimated_cost") or 0)
        total_cost += cost
        total_calls += 1
        total_input += int(row.get("input_tokens") or 0)
        total_output += int(row.get("output_tokens") or 0)
        if row.get("success"):
            successes += 1
        else:
            failures += 1

        stage = row.get("stage", "unknown")
        by_stage[stage] = by_stage.get(stage, 0) + cost

        model = row.get("model", "unknown")
        by_model[model] = by_model.get(model, 0) + cost

    return {
        "day": day,
        "client": client,
        "total_cost_usd": round(total_cost, 6),
        "total_calls": total_calls,
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "successes": successes,
        "failures": failures,
        "by_stage": {k: round(v, 6) for k, v in
                     sorted(by_stage.items(), key=lambda kv: -kv[1])},
        "by_model": {k: round(v, 6) for k, v in
                     sorted(by_model.items(), key=lambda kv: -kv[1])},
    }


# --------------------------------------------------------- CLI

def main(argv=None):
    p = argparse.ArgumentParser(
        prog="python scripts/task151_ai_spend_writer.py")
    p.add_argument("--json", action="store_true",
                   help="Read one JSON row from stdin and append it")
    p.add_argument("--report", action="store_true",
                   help="Print a summary report")
    p.add_argument("--day", help="Filter report to this day (YYYY-MM-DD)")
    p.add_argument("--client", help="Filter report to this client")
    p.add_argument("--path", help="Ledger file path (default: auto-detect)")
    a = p.parse_args(argv)

    if a.report or a.day or a.client:
        out = report(day=a.day, client=a.client, path=a.path)
        print(json.dumps(out, indent=2))
        return 0

    if a.json:
        raw = sys.stdin.read().strip()
        if not raw:
            print("no input", file=sys.stderr)
            return 1
        data = json.loads(raw)
        row = record_call(path=a.path, **data)
        print(json.dumps(row, indent=2))
        return 0

    p.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
