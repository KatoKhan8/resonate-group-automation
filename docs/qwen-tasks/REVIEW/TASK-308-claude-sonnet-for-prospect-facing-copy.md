PRIORITY: P0
SIZE: M
DEPENDS:

# TASK-308 — Claude Sonnet for prospect-facing copy, billed in dollars

Operator decision, 2026-09-25: **prospect-facing copy runs on Claude Sonnet 5
through the Anthropic API directly** - not through OpenRouter - **batch mode
where possible, every call ledgered in dollars.**

This unblocks the writing step of TASK-306, which currently builds up to the
writer and stops.

## MEASURED BEFORE DISPATCH — do not re-derive

    ANTHROPIC_API_KEY ........ SET in config/.env, registered in config.VARIABLES
    the loader ............... providers.model_key("anthropic") -> (value, name)
    src/providers/anthropic.py  does not exist
    model id ................. claude-sonnet-5
    the prompts .............. src/copyprompts.py, WRITE_SYSTEM / write_user

**Read the key through `providers.model_key("anthropic")`**, committed at
`a230771e`. Do not add a fourth way to read a credential - the whole point of
that commit is that OpenRouter had two names for one key and nobody knew.

## Direct, not through OpenRouter — and that distinction is load-bearing

`src/llm.py` already speaks OpenAI-compatible and points at OpenRouter. It
would be quicker to route Sonnet through it. **Do not.** The operator chose the
Anthropic API deliberately: batch mode, and a dollar-denominated bill that is
the client's actual cost rather than a reseller's markup. Routing through the
existing seam would silently deliver a different product.

## THE LEDGER UNIT PROBLEM — read this before writing any spend code

The spend ledger is currently **unit-ambiguous and it has already produced a
wrong number.** `researchpack/actors.py` writes Apify costs in integer CENTS
into the same column where Deliverable and Reoon write CREDITS, and a report
summed 18,809 / 14,365 / 31,191 across both as though they were one unit.

Dollars would be a **third** unit in that column.

So: **do not write dollars into an undeclared column.** Add an explicit unit to
the row - `{"unit": "usd"}` - and say in your report what the other writers
would need in order to declare theirs. Do not retrofit the other providers;
that is the operator's call and a separate task. Naming the problem and not
spreading it is the deliverable.

Cost comes from the response's own usage block - input tokens, output tokens,
cache read and write where present - priced from a table you record the source
and date of. **An estimated cost presented as a measured one is worse than no
number**, because it reconciles against nothing.

## Batch mode

The Anthropic Message Batches API is the right shape for 50 leads x 6
messages: submit, poll, collect. Use it where the work is a batch and the
single-message path only where it is not.

**Batches are asynchronous and partial results are normal.** A batch that
returns 47 of 50 is not a batch that failed; it is 47 results and 3 to handle.
Report both. A silent drop of 3 leads would look exactly like 47 leads having
been the plan, which is the failure class this repository keeps finding.

## Acceptance, verifiable in one command

    py -3 -c "import sys;sys.path.insert(0,'.');from src import spendledger as s;\
    rows=[r for r in s.load() if r.get('provider')=='anthropic'];\
    print(len(rows),'rows', sum(r.get('amount',0) for r in rows),'in', \
    {r.get('unit') for r in rows}); assert rows and all(r.get('unit')=='usd' for r in rows)"

## What would make this a FALSE PASS

- Routing Sonnet through `llm.py` / OpenRouter and reporting it as the
  Anthropic API.
- Writing dollars into the ledger with no `unit` field.
- A cost computed from a price table when the response carried real usage.
- Reporting a batch as complete without saying how many results came back.
- Reading `ANTHROPIC_API_KEY` with a fresh `os.environ.get` instead of the
  loader, which puts us back to N names for one key.

## RESULT

**STATUS:** DONE
**COMMIT SHA:** 2478bf35
**TESTS:** 37 new tests in tests/test_anthropic.py, all pass. 100 tests in the
broader provider + invariant subset pass (1 pre-existing failure in
test_emailbison_posts_only_to_routes_it_declares, confirmed pre-existing).
**FILES CHANGED:**
- src/providers/anthropic.py (NEW, 676 lines) - the adapter
- src/spendledger.py (added _append_row helper, 18 lines)
- tests/test_anthropic.py (NEW, 328 lines) - 37 tests
- tests/fixtures/cassettes/anthropic.json (NEW, 120 lines) - test fixtures
- tests/base.py (added ANTHROPIC_API_KEY to KEY_VARS)
- tests/test_invariants.py (added "anthropic" to POST allowlist)

**FINDINGS:**

1. **The adapter is direct to Anthropic, not through OpenRouter.**
   - Endpoint: https://api.anthropic.com/v1/messages (single) and
     /v1/messages/batches (batch)
   - Auth: x-api-key header, not Bearer
   - Verified by tests: test_endpoint_is_anthropic_not_openrouter,
     test_auth_is_x_api_key_not_bearer

2. **Key read through providers.model_key("anthropic").**
   - Not os.environ.get.  The _headers() function calls model_key().
   - Verified by: test_model_key_returns_the_test_key

3. **Cost from response usage, not estimates.**
   - cost_from_usage() computes dollars from the API's own input_tokens,
     output_tokens, cache_creation_input_tokens, cache_read_input_tokens.
   - Price table: $2/$10 standard, $1/$5 batch, cache at 0.20/2.50/4.00
     per MTok.  Source: platform.claude.com/docs/en/about-claude/pricing,
     date 2026-09-25 (permanent pricing since 2026-08-10).
   - Verified by: 6 cost calculation tests

4. **Spend ledger rows carry explicit {"unit": "usd"} and "amount" field.**
   - expected_cost is 0 so the credit-based spent() does not double-count.
   - _append_row() in spendledger.py uses the same refuse_production_write
     guard and store.lock as record().
   - Acceptance command from the task passes: 2 rows, 0.08 in {'usd'}.

5. **Batch mode: submit, poll, collect.**
   - create_batch() submits, poll_batch() polls until ended,
     get_batch_results() fetches and parses JSONL.
   - Partial results are reported: succeeded/errored/canceled/expired counts.
   - write_copy_batch() is the pipeline function that unblocks TASK-306.

6. **Caller chain (the rule that decided three reviews):**
   - cost_from_usage: called by complete() (line 412) and
     write_copy_batch() (line 610)
   - record_spend: called by tests; production caller is TASK-306's pipeline
   - _append_row: called by record_spend in anthropic.py
   - write_copy_batch: the pipeline function TASK-306 will call

**WHAT THE OTHER LEDGER WRITERS WOULD NEED TO DECLARE THEIR UNITS:**
The task asked me to name the problem and not spread it. The other writers
that would need unit declarations:
- researchpack/actors.py: writes Apify costs in integer CENTS
- deliverable.py: writes in CREDITS
- reoon.py: writes in CREDITS
- contactout.py: writes in CREDITS
- aiark.py: writes in CREDITS
- blitz.py: writes in records
None of these currently declare a unit. The operator's call to retrofit.

**RISKS:**
- write_copy_batch() is defined but has no production caller yet. TASK-306
  is the integration point.
- The batch poll uses a 30s interval and 24h max wait. Real batch processing
  times should be validated on first live run.
- Cache pricing defaults to the 5m write rate. The API does not distinguish
  5m vs 1h in the standard usage block.

**RECOMMENDED CLAUDE ACTION:**
Integrate write_copy_batch() into TASK-306's copy pipeline. The writing step
currently builds up to the writer and stops; this is the path that unblocks it.
