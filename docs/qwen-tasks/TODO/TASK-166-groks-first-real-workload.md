PRIORITY: P1
DEPENDS:

# TASK-166 - Grok's first real workload, measured against what we already have

## WHERE THIS SITS

TASK-157 built `src/providers/xai.py`: allowlist, bounds, trimmed returns,
usage and cost capture, bounded retry, 42 tests against a fake transport.
`GROK_AUTH_OK` is established. `grep -rn "xai" src/` returns only the adapter
itself - deliberately, because wiring it into a production path was Claude's
call, not the worker's.

It has never processed a real record. An adapter with no caller is a cost we
have paid and not collected on.

Grok exists to take expensive research away from Claude and to answer the
questions Qwen cannot: current company facts, recent developments, web and X
signals, ambiguous ICP.

## THE QUESTION

Run Grok against real domains and measure whether its research is better than
what the free path already produces.

1. Pick **10 domains** from the estate with `company_facts` already populated
   from the existing webfetch/Apify path. Ten, not more - this spends real xAI
   money and the point is a measurement, not a batch.
2. For each, ask Grok the company-research question the pipeline actually asks.
   Read `src/research.py` and `src/generate.py` for the real shape - do not
   invent a prompt the pipeline would never send. Enable `web_search`; that is
   the capability we are buying.
3. Compare, per domain, against the existing evidence:
     - facts the existing path has and Grok confirms
     - facts Grok has that the existing path does not
     - facts the two CONTRADICT
     - facts Grok asserts with no source URL
4. Report the measured cost. The adapter captures `cost_in_usd_ticks`
   (10B ticks = $1) and `server_side_tool_usage`. Give cost per domain and the
   projection to 316 domains.

## THE TRAP

A claim without a source URL cannot pass the claims gate, so it cannot reach
copy, so it is worth nothing to this pipeline however true it is. Count those
separately and do not let them inflate the "facts Grok found" number.

The contradictions are the most valuable output of this task. Do not resolve
them yourself and do not average them - record both sides with both sources and
hand them to Claude.

## WHAT YOU MAY NOT DO

- Read `XAI_API_KEY` from the environment only. Never print it, never commit
  it, never put it in a log or a doc. Env var NAME only.
- Do not wire Grok into `qualify`, `generate`, `research` or any production
  path. Measure through a script.
- Do not exceed 10 domains and do not retry a failed domain more than twice.
- Do not commit a real domain, company name or URL in the deliverable if the
  existing PII rules cover it - hash what they cover, and say what you hashed.
- Do not report a predicted result. You have the key. Call the API.

## FILES ALLOWED

    scripts/task166_*.py
    docs/GROK-VS-FREE-RESEARCH-2026-09-16.md   (new)

## FILES FORBIDDEN

    src/   work/   config/

## DELIVERABLE

The per-domain comparison, the four counts, the contradictions with both
sources, the measured cost per domain and the 316-domain projection, and a
plain verdict: is Grok worth its price on company research, yes or no.
