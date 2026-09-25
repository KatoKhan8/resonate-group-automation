PRIORITY: P0
SIZE: M
DEPENDS: TASK-309

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

## ADDED 2026-09-25 — the cost shape is decided and measured

Operator: under **0.3 cents per lead**, without lowering what the prospect
reads. `src/copyprompts.py` is already built to that shape and the numbers are
measured, not projected:

    COHORT_SYSTEM (cached once per batch) ...... 696 tokens
    per-lead user turn (paid every lead) ........ 61 tokens   cap 1,500
    output, spans only .......................... 315 tokens   cap 400

**Sonnet writes only the spans that vary** - subject, first line, four bridge
sentences, two LinkedIn messages. The standing paragraphs come from
`productive.yaml` and the pipeline joins them. The prospect reads identical
words; we simply do not pay a frontier model to retype approved copy.

Cost at assumed list pricing ($3/$15 per M, cache read $0.30), **which you must
confirm from the provider before quoting it as fact**:

    spans only + cached + batch  ....... 0.256c   <- MEETS the target
    spans only + cached, no batch ...... 0.512c
    spans only + batch, uncached ....... 0.350c
    FULL BODIES + cached + batch ....... 0.607c

**All three levers are load-bearing. Drop any one and the target is missed.**
Output is 92% of the cost, so output tokens are the whole game - a prompt
change that adds output is a cost change.

Cache the system prompt at the cohort boundary. One call per lead for every
step. `max_tokens` capped at 400. **No retry without a changed input** - a
retry on identical input buys an identical answer at full price.

Report per batch, in the PROGRESS block, the split by model and the measured
cents per lead from the LEDGER, never from this projection.
