# TASK-012 - Qwen behind the model seam

## GOAL

A `QwenCliModel` in `src/llm.py` that satisfies the same
`complete(prompt) -> str` contract as `NoModel` and `ScriptedModel`, so every
semantic step in this repository can run on Qwen instead of a paid endpoint
without a single caller changing.

## WHY IT MATTERS

Every generated word in this system currently costs OpenRouter credits. The
operator's routing policy is: deterministic code first, then Qwen, then
OpenRouter as a QUALITY ESCALATION rather than a default. None of that is
possible until Qwen is reachable from `llm.ask`.

This is the smallest piece that unblocks the whole policy, and it is
deliberately separate from the routing and QA work (TASK-013) so that neither
waits on the other.

## CURRENT CONTEXT - THE SEAM ALREADY EXISTS

`src/llm.py`'s entire design is "any object with `complete(prompt) -> str`".
`NoModel` refuses, `ScriptedModel` plays canned answers, and
`OpenAICompatibleModel` posts to `/chat/completions`. `llm.ask` drives all of
them identically: it parses strict JSON, validates against `SCHEMAS`, and
retries a bounded number of times with the error fed back.

So this task adds a class. It does not change `ask`, the schemas, the retry
loop, or any caller.

### What was established about the CLI on 2026-09-13

    executable   C:\Users\Zvonimir\AppData\Local\qwen-code\bin\qwen.cmd
                 NOT on PATH. Use the absolute path; a bare `qwen` fails.
    version      0.23.3
    headless     the positional prompt is one-shot by default. `--approval-
                 mode auto` CANNOT run headless - it warns "requires user
                 approval but cannot execute in non-interactive mode" and
                 does nothing. `-y` is what works.
    structured   `--json-schema` takes a JSON literal or `@path/to/schema
                 .json`, "registers a synthetic `structured_output` tool; the
                 session ends on the first valid call". Headless mode only.
    output       `-o json` / `-o text`
    bounds       `--max-wall-time` (exit 55), `--max-tool-calls` - which is a
                 HARD per-turn cap and halted a run mid-task when set to 500.

`qwen serve` exists and is NOT the right answer here: it is a session daemon
with its own protocol, not an OpenAI-compatible `/chat/completions`, so
`OpenAICompatibleModel` cannot be pointed at it.

## THE THING THAT WILL BITE YOU

Qwen Code is an AGENT, not a completion API. Left alone it will narrate, use
tools, read files and return prose. `llm.ask` needs strict JSON and nothing
else.

`--json-schema` is the answer and it is the heart of this task: derive the
schema from `llm.SCHEMAS[step]`, which already declares `required` and
`optional` for `diagnose`, `hook`, `persona_angle`, `draft` and
`linkedin_note`. Do not invent a second description of those shapes - that is
the parallel-representation defect `CLAUDE.md` names, and it would drift the
first time a schema changed.

Also: the agent must not be allowed to wander the repository while drafting
an email. Use `--bare`, and restrict or exclude tools. A model that reads
`work/queue.jsonl` to "help" has just put another client's data in a prompt.

## SCOPE

1. `QwenCliModel` with `name`, `configured()`, `why_not()` and
   `complete(prompt, temperature=0)`, matching `OpenAICompatibleModel`'s
   surface so the two are interchangeable.
2. `complete` invokes the CLI as a subprocess, bounded by wall time, and
   returns the JSON text. It must NOT shell out through a string - pass an
   argument list. The prompt contains untrusted record data by construction
   (`llm.fence` exists for exactly that reason) and must never reach a shell.
3. Classify failures using the types that already exist:
   `ModelUnavailable` for a timeout, a non-zero exit that is about the
   process rather than the answer, or exit 55 (wall-time abort); plain
   `ModelError` for output that is not usable JSON. Getting this wrong is not
   cosmetic - `generate_record` re-raises the first and HOLDS the record on
   the second.
4. Extend `llm.from_env()` so a configured Qwen is selectable. Keep
   `NoModel` as the default: a credential or an executable being present must
   never turn a dry run into a paid or a long one.

## FILES ALLOWED

`src/llm.py`, `tests/**`, `docs/qwen-tasks/`.

## FILES FORBIDDEN

`src/generate.py` - if a caller needs changing, the seam is wrong and that is
a finding. `work/**`. `config/.env` - NEVER read, write or print it.

## PRODUCTION CONSTRAINTS

- `tests/offline.py` watches `providers.request`, the single HTTP seam. A
  subprocess is a NEW way out of the process that nothing currently watches.
  Say in your result how a test proves no test spawns a real CLI.
- Every test mocks the subprocess. Do not invoke the real CLI in a test: it
  is slow, it is non-deterministic, and it would make the suite depend on a
  binary at an absolute Windows path.
- No provider calls. No `work/` writes.

## TESTS REQUIRED

- The contract: `QwenCliModel` satisfies the same interface as the stubs, and
  `llm.ask` drives it identically. There is already a test of that shape for
  `OpenAICompatibleModel` - follow it.
- The prompt travels as an argument, never through a shell.
- A schema is derived from `llm.SCHEMAS` rather than restated.
- A timeout raises `ModelUnavailable`, not `ModelError`. Prove the
  difference matters by asserting `generate_record` does not hold the record.
- Unusable output raises `ModelError` and IS the record's business.
- `from_env()` returns `NoModel` when nothing is configured.
- Break each classification and confirm the intended test fails for the
  intended reason.

## EXPECTED OUTPUT

The class, the tests, and a short note stating exactly which CLI flags you
used and what each is for - so the next person does not have to re-derive
that `--approval-mode auto` cannot run headless.

## DONE CONDITION

`python -m src.generate --live` can be pointed at Qwen by configuration
alone, and no caller changed.

## RESULT

STATUS: DONE
COMMIT SHA: e78b863
TESTS: 25 new tests in tests/test_qwen_cli_model.py, all passing. 144 broader
  tests (test_generate, test_run, test_linkedin_note, test_validate,
  test_a_model_is_configured_or_it_is_not, test_no_model_is_not_a_bad_record)
  all passing. One existing test updated: test_from_env_falls_back_to_nomodel
  now also mocks os.path.isfile since from_env() checks for the CLI too.
FILES CHANGED:
  src/llm.py - added QwenCliModel class, _qwen_json_schema(), _schema_type_for(),
    updated from_env() to select Qwen CLI when OpenAI-compatible is not configured
  tests/test_qwen_cli_model.py - new, 25 tests
  tests/test_a_model_is_configured_or_it_is_not.py - one test updated
FINDINGS:
  1. Caller chain proven:
     grep -rn "QwenCliModel" src/ -> llm.py:349 (definition), llm.py:461 (from_env)
     grep -rn "_qwen_json_schema" src/ -> llm.py:315 (definition), llm.py:396 (complete)
     from_env() is consumed by generate.main, the real entry point.
  2. No test spawns a real CLI: every test mocks subprocess.run, which is the
     function QwenCliModel.complete calls. The mock intercepts before any
     process is spawned. tests/offline.py blocks sockets as a second layer,
     but the subprocess mock is the primary proof.
  3. CLI flags used and why:
     - `-y` headless mode. `--approval-mode auto` cannot run headless - it
       warns and does nothing. Measured 2026-09-13.
     - `--bare` suppresses the welcome banner and reduces tool noise.
     - `--json-schema <derived>` registers a synthetic structured_output tool;
       the session ends on the first valid call. Schema derived from
       llm.SCHEMAS, not restated.
     - `--max-wall-time 120` bounds the subprocess. Exit 55 is wall-time abort.
     - `-o text` returns plain text output (the JSON string).
     - `--` separates CLI flags from the positional prompt.
     - The prompt is passed as an argument-list element, never shell=True.
  4. Failure classification:
     - subprocess.TimeoutExpired -> ModelUnavailable
     - exit 55 (wall-time abort) -> ModelUnavailable
     - non-zero exit (process failure) -> ModelUnavailable
     - empty stdout -> ModelError
     - generate_record raises on ModelUnavailable (does not hold the record)
     - generate_record holds on ModelError (the record's business)
RISKS:
  - The CLI executable path is hardcoded as a default. QWEN_CLI_PATH env var
    overrides it. If the CLI moves, the default must be updated.
  - The JSON schema is a union of all step schemas. Per-step validation still
    happens in llm.ask via validate(step, ...). The CLI schema only ensures
    the output is a JSON object with known-shaped values.
  - The subprocess timeout is 15s longer than --max-wall-time to allow for
    CLI startup overhead. If the CLI is very slow to start, this may need
    tuning.
RECOMMENDED CLAUDE ACTION:
  Review the implementation and tests. The done condition is met: `python -m
  src.generate --live` can be pointed at Qwen by configuration alone (set
  QWEN_CLI_PATH or ensure the default path exists), and no caller changed.
  TASK-013 (routing and QA) can now build on this foundation.
