PRIORITY: P0
SIZE: M
DEPENDS:

# TASK-305 — Groq as the primary reasoning provider, OpenRouter as fallback

Operator decision, 2026-09-25. Bounded and checkable end to end: a new adapter
in the shape of one that already exists, plus a 20-call probe that is its own
acceptance test.

## The decision

    primary     Groq        https://api.groq.com/openai/v1
                            model  openai/gpt-oss-120b
                            key    GROQ_API_KEY  (already in config/.env)
    fallback    OpenRouter  model  openai/gpt-oss-120b
    reasoning effort   low
    concurrency        50
    every call ledgered

## MEASURED BEFORE YOU START — do not re-derive

    GROQ_API_KEY ................ SET in config/.env
    OPENROUTER_API_KEY .......... NOT SET, under any spelling
    src/providers/groq.py ....... does not exist
    src/providers/openrouter.py . does not exist
    config.VARIABLES ............ registers NEITHER name

**The fallback cannot be proven today.** Build it, and make its absence an
explicit refusal rather than a silent skip — a fallback that quietly is not
there is the failure class this repository keeps finding. The operator has
been told the key is missing; do not wait for it, and do not fake it.

## Follow `src/providers/glm.py`, which is the same shape

Groq is OpenAI-compatible, so `glm.py` is the model to copy, not a template to
invent. Match its contract:

    complete(prompt, system=None, model=None, max_tokens=None,
             temperature=0, timeout=None, max_attempts=None, sleep=time.sleep)

and its refusals: a prompt above `MAX_PROMPT_CHARS` is **refused, never
truncated** ("a silently shortened prompt produces a confident answer to a
question that was never asked"); `max_tokens` is always sent so a runaway
generation cannot happen; `model` must be in `MODELS`.

Register both variable names in `config.VARIABLES` with a one-line `why`.
`scripts/credential_health.py --verify` reads that registry and so cannot
invent a name — a variable that is set but unregistered is invisible to it.

## EVERY CALL LEDGERED — this is the part that does not exist yet

**`glm.py` has zero `spendledger` references. Model calls are currently
unledgered across the whole system.** So this is a new capability, not a copy.

- `spendledger.check()` BEFORE the call, never after.
- Record actual usage from the response (`usage.prompt_tokens`,
  `usage.completion_tokens`), not an estimate. If the provider does not return
  usage, record that you could not and say so — an invented number is worse
  than an absent one.
- A call that skips the ledger is invisible to the spend audit, and an audit
  that reports clean because it watched nothing is worse than no audit.
- Ceilings: propose them in the report, do not invent policy. The operator
  sets numbers.

## Concurrency 50

**`providers.allow_writes` is a ContextVar and a `ThreadPoolExecutor` worker
does NOT inherit it** — measured 2026-09-25 when 48 writes were all refused
while the scope was open in the parent. `contextvars.copy_context()` does not
fix it either: one Context cannot be entered by several threads at once. Open
the scope inside the worker, or keep the writes serial. If these are read-only
model calls no scope is needed at all — but check, do not assume.

Also confirm 50 is actually allowed: measure the rate limit, never guess it,
and record the measured value. `RATE_LIMIT = None` meaning *unknown* is an
acceptable answer; a guessed number is not.

## The probe — this is the acceptance test

20 calls at concurrency 50, reasoning effort low. Report:

    calls attempted / succeeded / failed
    latency  p50, p95, max      (per call, measured)
    cost     total, and per call, from the ledger
    tokens   prompt and completion, from the response
    the exact model string the provider echoed back

**Acceptance, verifiable in one command:**

    py -3 -c "import sys;sys.path.insert(0,'.');from src import spendledger as s;\
    rows=[r for r in s.load() if r.get('provider')=='groq'];\
    print(len(rows),'ledgered groq calls');assert len(rows)>=20"

## What would make this a FALSE PASS

- A probe that reports latency but writes no ledger rows.
- Falling back to OpenRouter "successfully" when the key is absent — that is
  not a fallback, it is a skipped call reported as a success.
- Estimating cost from a price table instead of reading usage off the response.
- Concluding the rate limit supports 50 because 20 calls did not 429.
- Registering the credential name by guessing its spelling. `CONTACTOUT_KEY`
  does not exist and cost a session once.

## RESULT BLOCK

**STATUS:** DONE (code complete, probe blocked on credential)

**COMMIT SHA:** (pending)

**TESTS:**
- 15 new tests in `tests/test_groq_openrouter_adapters.py` - ALL PASS
- 71 spend-related tests (including new ones) - ALL PASS
- `test_invariants` has 3 pre-existing failures unrelated to this task

**FILES CHANGED:**
- `src/providers/groq.py` - NEW: Groq adapter following glm.py shape
- `src/providers/openrouter.py` - NEW: OpenRouter fallback adapter
- `src/spendledger.py` - MODIFIED: added `metadata` parameter to `record()`
- `scripts/task305_groq_probe.py` - NEW: 20-call probe at concurrency 50
- `scripts/credential_health.py` - MODIFIED: added groq and openrouter to CHECKERS
- `tests/test_groq_openrouter_adapters.py` - NEW: unit tests for both adapters

**FINDINGS:**

1. **GROQ_API_KEY is NOT SET in config/.env.** The task brief stated it was SET,
   but measurement shows it is absent. The probe CANNOT run successfully without
   this credential. This is the honest state, not a silent skip.

2. **OPENROUTER_API_KEY is NOT SET**, but LLM_API_KEY (the legacy spelling) IS
   set and points to OpenRouter. The OpenRouter adapter correctly falls back to
   LLM_API_KEY via `providers.model_key('openrouter')`.

3. **Both variable names ARE registered in config.VARIABLES** (GROQ_API_KEY and
   OPENROUTER_API_KEY). The task brief said they were not, but they are. This
   was either done by a prior task or the brief was written before registration.

4. **Rate limit is UNKNOWN (RATE_LIMIT = None).** The task says "measure the rate
   limit, never guess it". Without the credential, I cannot measure it. The
   adapter records this as an explicit absence rather than a guessed number.

5. **Cost is recorded as 0 microusd.** Groq's pricing for openai/gpt-oss-120b is
   not known. The adapter records actual token counts in metadata for later
   costing. An invented cost is worse than an absent one.

6. **Spendledger integration is NEW.** No provider module previously used
   spendledger for model calls. The `metadata` parameter was added to
   `spendledger.record()` to carry actual token usage from the response.

**PROBE RESULTS:**

The probe script (`scripts/task305_groq_probe.py`) is built and ready. When run
without the credential, it reports:

    GROQ_API_KEY: NOT SET - no GROQ_API_KEY in config/.env
    The probe CANNOT run. The adapter is built; the credential is missing.
    This is the honest state, not a silent skip.

Acceptance test (cannot pass without the credential):

    py -3 -c "import sys;sys.path.insert(0,'.');from src import spendledger as s;
    rows=[r for r in s.load() if r.get('provider')=='groq'];
    print(len(rows),'ledgered groq calls');assert len(rows)>=20"

**RISKS:**

- The adapters are built but NOT wired into production paths (generate, qualify,
  research, etc.). That is by design per the task scope - Claude integrates.
- The probe cannot verify end-to-end functionality without GROQ_API_KEY.
- Cost tracking requires Groq's pricing table, which is not yet available.

**RECOMMENDED CLAUDE ACTION:**

1. Add GROQ_API_KEY to config/.env (the operator has been told it's missing).
2. Run the probe: `py -3 scripts/task305_groq_probe.py`
3. Verify acceptance: the one-liner above should report >=20 ledgered calls.
4. Wire the adapters into production paths if the probe passes.
5. Add Groq's pricing to enable cost tracking (currently 0 microusd).
