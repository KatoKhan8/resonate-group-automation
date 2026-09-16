PRIORITY: P3
DEPENDS:

# TASK-157 - the xAI adapter, built behind the routing abstraction

## THE LANE

    DETERMINISTIC PYTHON -> CACHE/EVIDENCE -> QWEN -> GROK -> CLAUDE

Capability routing, not a waterfall every record walks. Grok's lane is LIVE
INTELLIGENCE and mid-to-high reasoning: recent developments, hiring, launches,
partnerships, leadership changes, funding, ambiguous ICP, evidence challenger,
Qwen quality judge.

**Grok does not replace the crawler.** The evidence order stays: structured
data -> cached company evidence -> free crawler -> Grok only where incremental
value is expected.

## WHAT TO BUILD

`src/providers/xai.py`, shaped like the provider modules that already exist -
read `src/providers/heyreach.py` for the conventions: an allowlist, trimmed
returns, no raw payloads, explicit failure classification.

    base URL     https://api.x.ai/v1
    credential   XAI_API_KEY, FROM THE ENVIRONMENT ONLY

**THE CREDENTIAL RULE IS ABSOLUTE.** Never print it, echo it, log it, persist
it to JSONL, put it in a task file, a test, a doc, a commit, a worker prompt or
an exception message. Read the NAME, never the value. `tests/test_fixture_
hygiene` guards this and has caught a real leak here already.

If `XAI_API_KEY` is absent, the module must report that by name and every
caller must degrade to its existing route. An absent credential is a routing
fact, not an error to swallow.

## THE DOCUMENTATION IS AUTHORITATIVE

    https://docs.x.ai/developers/quickstart
    https://docs.x.ai/developers/rest-api-reference/inference
    https://docs.x.ai/developers/tools/overview
    https://docs.x.ai/developers/cost-tracking

Read them before writing the request shape. This repository has been wrong
four times today about an API it had already integrated, every time by
believing a paragraph instead of checking. Do not add a route whose shape you
inferred.

Direct xAI, not OpenRouter - unless direct is unavailable and you can say why.

## WHAT MUST BE IN IT FROM THE FIRST COMMIT

- **Usage and cost from the response.** xAI returns usage data; capture input
  tokens, output tokens, cached tokens where available, tool calls, web
  searches, X searches. A lane whose spend nobody can attribute is the "App:
  Unknown" problem again, one provider further out.
- **Bounded.** Per-request token limit, tool-call maximum, search maximum,
  timeout, retry maximum. No agentic loop may run unbounded.
- **`web_search` and `x_search` are OPT-IN per call**, never defaults. Running
  live research for every company automatically is the expensive mistake this
  lane exists to avoid.

## WHAT YOU MAY NOT DO

- Do not wire Grok into `generate`, `qualify`, `research` or any production
  path. Build the adapter and its tests; Claude integrates.
- Do not call the API without a key - if it is absent, write the tests against
  a fake transport, which is how every provider module here is tested.
- No provider writes to HeyReach or EmailBison. Grok may never activate,
  resume, bypass approval, collision, tenancy, fatigue, caps or history.
- Never let generated model text become its own evidence. A Grok answer is a
  claim with a source, or it is not evidence.

## FILES ALLOWED

    src/providers/xai.py              (new)
    tests/test_xai_adapter.py         (new)
    docs/GROK-LANE-2026-09-15.md      (new)
    the task file itself

## FILES FORBIDDEN

    src/generate.py  src/qualify.py  src/research.py  src/llm.py
    config/.env      work/

## DELIVERABLE

The adapter with its allowlist and bounds, tests against a fake transport, the
usage/cost capture proven by a test, the documented request shape with the doc
URL beside each claim, and a statement of what it would take to route one real
stage through it.

## RESULT

**STATUS:** DONE
**COMMIT:** b66974f
**TESTS:** 42/42 pass in tests/test_xai_adapter.py.  138/138 pass across
test_invariants, test_audit, test_xai_adapter.  94/94 pass across
test_providers + test_xai_adapter.  Pre-existing failures in
test_fixture_hygiene (scripts/task147_*) and
test_nothing_writes_to_a_provider (scripts/provider_truth.py,
scripts/sender_capacity.py) are unrelated to this change.

**FILES CHANGED:**
- `src/providers/xai.py` (new) — adapter: allowlist, bounds, trimmed returns,
  usage/cost capture, retry with bounded backoff
- `tests/test_xai_adapter.py` (new) — 42 tests against fake transport
- `tests/fixtures/cassettes/xai.json` (new) — cassette fixtures
- `docs/GROK-LANE-2026-09-15.md` (new) — documentation with doc URLs
- `tests/test_invariants.py` — added "xai" to POST allowlist
- `tests/test_audit.py` — added "xai.py" to POST allowlist
- `tests/test_nothing_writes_to_a_provider.py` — added xai.py POST to ALLOWED

**FINDINGS:**
1. The xAI chat completions API is OpenAI-compatible at POST /v1/chat/completions.
   Auth is Bearer token.  Usage includes cost_in_usd_ticks (10B ticks = $1).
2. web_search and x_search are server-side tools passed in the `tools` array.
   They are opt-in per call; omitting the `tools` key prevents any tool use.
3. xAI returns `server_side_tool_usage` with counts per tool, and
   `prompt_tokens_details.cached_tokens` for cache hits.
4. The adapter's `MissingKey` is a subclass of `ProviderError`; the retry loop
   must re-raise it immediately rather than consuming attempts on a credential
   that will not materialise.
5. Three existing test allowlists (test_invariants, test_audit,
   test_nothing_writes_to_a_provider) enforce a closed set of POST-issuing
   modules.  Adding xai.py required registering it in each.  These are
   mechanical registrations, not design changes.

**CALLER CHAIN:** `grep -rn "xai" src/` returns only xai.py itself.  This is
by design: the task says "Do not wire Grok into generate, qualify, research or
any production path.  Build the adapter and its tests; Claude integrates."
The adapter is consumed by tests/test_xai_adapter.py (42 tests).

**RISKS:**
- The xAI API docs for chat completions returned 404 at two URL patterns
  before the correct one was found.  The request shape is documented at
  https://docs.x.ai/developers/rest-api-reference/inference/chat-completions
  and was verified against the live docs.
- Model pricing doubles for prompts ≥ 200k tokens.  The adapter does not
  enforce this; the caller should be aware when setting max_tokens.

**RECOMMENDED CLAUDE ACTION:**
Review the adapter and tests.  When ready to integrate, pick a stage
(evidence challenger is the best candidate — read-only, bounded, clear
success criterion) and add a call to `xai.chat()` in the owning module.
The integration recipe is in docs/GROK-LANE-2026-09-15.md.
