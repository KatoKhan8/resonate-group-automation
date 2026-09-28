# TASK-457 — Independent verification of TASK-305

## Review metadata

    reviewed task       TASK-305
    reviewed branch     qwen-worker-9-r9
    branch HEAD SHA     f1b9c357c17f4b557cbdb06f68339c7343ef3e83
    SHA verified        YES — `git rev-parse qwen-worker-9-r9` returned
                        f1b9c357c17f4b557cbdb06f68339c7343ef3e83, matching the
                        task file. Branch has not moved.
    review worktree     .qwen/worktrees/task-457-review (detached at f1b9c357)
    reviewer            Qwen (GLM role), 2026-09-28
    protocol            docs/GLM-REVIEW-PROTOCOL.md

## What TASK-305 claims

TASK-305 built two new provider adapters:

- `src/providers/groq.py` — Groq as primary reasoning provider
- `src/providers/openrouter.py` — OpenRouter as explicit-refusal fallback

Plus 19 unit tests in `tests/test_groq_openrouter_adapters.py` and two lines
in `scripts/credential_health.py` registering the credential names.

The result block claims STATUS: DONE (code complete, tests pass, live probe
BLOCKED). The live probe was not run because GROQ_API_KEY is absent from this
worktree.

## Finding 1 — DISCONNECTED: zero production callers

**Severity: CRITICAL — rework, not merge.**

Exhaustive search of the entire codebase at `f1b9c357`:

    grep -rn "fallback_complete\|groq\.complete\|openrouter\.complete" . --include="*.py"

Returns ONLY:
- The definitions themselves in `src/providers/groq.py` (lines 361, 374)
- The test file `tests/test_groq_openrouter_adapters.py` (19 call sites)

**No production code in `src/` imports or calls `groq.complete`,
`openrouter.complete`, or `groq.fallback_complete`.**

The actual generation path is:

    src/generate.py → llm.ask() → src/llm.py → HttpModel.complete()

`HttpModel` in `src/llm.py` uses `LLM_BASE_URL`/`LLM_API_KEY`/`LLM_MODEL`
directly through `providers.request()`. It has a special case for OpenRouter
URLs (line 229-230) using `providers.model_key("openrouter")`, but it does
NOT delegate to the new `groq.py` or `openrouter.py` adapters.

The new modules are correct in isolation and completely unused by production.
This is the canonical "existence is not function" defect this repository has
been bitten by repeatedly (QWEN.md, CLAUDE.md, GLM-REVIEW-PROTOCOL.md
section 6.C).

**Falsification:** Delete `src/providers/groq.py` and
`src/providers/openrouter.py`. Run the full test suite. Every test except
`test_groq_openrouter_adapters.py` passes — because nothing else references
them. The 19 tests that DO reference them pass because they drive the
adapters through stubs, not through any production entry point.

## Finding 2 — Scope drift: unrelated src/ changes on the branch

The branch carries two modifications to existing `src/` files that are NOT
part of TASK-305:

1. `src/notify.py` — RETIRED_CHANNELS mechanism, `ops_channel()` rewrite to
   use STATUS_CHANNEL_VAR, retirement of `C0C34GCAR27`. This is a Slack
   routing fix from a different task.
2. `src/providers/slack.py` — `load_env()` added to `live()`. Also a Slack
   fix from a different task.

These are legitimate changes but they are not TASK-305's. Merging the branch
as-is would bring them in unreviewed. Cherry-pick is required:

    TASK-305 artifacts (4 files):
      src/providers/groq.py          (NEW)
      src/providers/openrouter.py    (NEW)
      scripts/credential_health.py   (2 lines added)
      tests/test_groq_openrouter_adapters.py  (NEW)

    NOT TASK-305 (would need separate cherry-pick):
      src/notify.py                  (36 lines changed)
      src/providers/slack.py         (13 lines changed)

## Finding 3 — Live probe not run (acknowledged by result block)

The 20-call acceptance probe was not executed. The result block states this
honestly: GROQ_API_KEY is absent from the worktree. The rate limit at
concurrency 50 is unmeasured. `RATE_LIMIT = None` (UNKNOWN) is an acceptable
answer per the task specification.

This is not a defect in the result block — it is an honest statement of what
is owed. The probe is Claude's to run from Claude's worktree.

**Not verified:** actual endpoint connectivity, real latency, real token
costs, rate limit at concurrency 50.

## Finding 4 — Tests are well-structured but test the island, not the wiring

The 19 tests cover:
- Request shape (bounded, addressed to /chat/completions, max_tokens sent)
- Prompt bound refused not truncated
- Unknown model refused
- Usage read from response (not estimated)
- Empty completion refused
- Failure classification (401 auth, 429 rate limit, 500 server, missing key)
- Ledger integration (successful call writes row, failed call writes none)
- OpenRouter explicit MissingKey when key absent
- Fallback wiring (tries Groq first, raises when both keys missing)

These are good contract tests. They drive the adapter through
`providers.set_transport` stubs and verify the adapter's behaviour in
isolation.

**How could these pass while the implementation is still wrong?** Easy: the
adapters could be (and are) completely disconnected from production. The
tests prove the adapter contract; they do not prove any production code path
reaches the adapter. Finding 1 is the consequence.

## Finding 5 — No deletion risk to src/ files

`git diff master...f1b9c357 --diff-filter=D --name-only` returns only two
task markdown files:

    docs/qwen-tasks/TODO/TASK-392-signature-per-attested-mailbox-verification.md
    docs/qwen-tasks/TODO/TASK-399-docs-hygiene-pass.md

No `src/`, `tests/`, or `scripts/` files would be deleted. The two new
adapter files are additive. The `src/notify.py` and `src/providers/slack.py`
changes are modifications, not deletions.

## Finding 6 — Credential registration is correct

`scripts/credential_health.py` adds two lines:

    "GROQ_API_KEY": "groq",
    "OPENROUTER_API_KEY": "openrouter",

These match the `ENV_KEY` constants in the respective adapter modules. The
spend ledger (`src/spendledger.py` line 153) already has unit mappings for
both providers on master. The provider key map (`src/providers/__init__.py`
lines 140-141) already registers both on master. No config.py change was
needed — the variable descriptions are already there.

## Disposition

| # | Finding | Severity | Evidence |
|---|---------|----------|----------|
| 1 | Zero production callers | CRITICAL | grep returns only definitions + tests |
| 2 | Scope drift (notify, slack) | MEDIUM | git diff --stat shows unrelated src/ changes |
| 3 | Live probe not run | INFO | Acknowledged in result block; owed |
| 4 | Tests test island not wiring | CRITICAL | Mutation: delete adapters, all other tests still pass |
| 5 | No deletion risk | OK | diff-filter=D shows only task markdown |
| 6 | Credential registration correct | OK | Names match ENV_KEY constants |

## Recommendation: REWORK

**Reason:** Finding 1 is disqualifying. Two well-written adapter modules with
19 passing tests and zero production callers is the exact defect pattern this
repository's operating contract warns against. The code is correct and
unused.

**What rework must produce before merge:**

1. A production caller. Either:
   - `src/llm.py`'s `HttpModel` delegates to `groq.complete()` / 
     `openrouter.complete()` based on the base URL, OR
   - `src/generate.py` calls `groq.fallback_complete()` directly, OR
   - A new entrypoint wires the adapters into the generation chain.
   
   The caller must be traceable: `grep -rn "groq\|openrouter" src/` must
   return more than just the adapter definitions and config registrations.

2. Scope separation. The `src/notify.py` and `src/providers/slack.py` changes
   must either be cherry-picked onto their own branch or removed from this
   one before merge.

3. The live probe, run from Claude's worktree where GROQ_API_KEY is set.

**What is good and should be preserved:**
- The adapter contracts (same shape as `glm.py`)
- The spend ledger integration (reserve/settle/release)
- The explicit refusal on missing key (both adapters)
- The fallback wiring in `fallback_complete()`
- The 19 unit tests
- The credential_health.py registration
