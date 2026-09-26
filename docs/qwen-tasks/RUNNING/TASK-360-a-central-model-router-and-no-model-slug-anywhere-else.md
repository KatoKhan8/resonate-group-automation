PRIORITY: P0
SIZE: L
DEPENDS:

# TASK-360 - a central model router, and no model slug anywhere else

**Operator scope 1, 2026-09-26**, from
`docs/OPERATOR-DIRECTIVES-2026-09-26-MODEL-ROUTING.md` section 15.

## Build

    config/model_policy.yaml   NEW, versioned
    src/modelrouter.py         NEW - resolves task_type -> routing decision
    src/llm.py                 MODIFY - reads the router, never a literal slug
    tests/test_no_model_slug_lives_outside_the_policy.py   NEW

`config/model_policy.yaml` maps **task_type** to provider, model, reasoning level,
fallback and max tokens, and carries a `version` field. The directive's own
example policy is the starting point:

    simple extraction        -> Groq / GLM Flash
    research synthesis       -> GLM Flash
    complex account strategy -> GLM high
    critical ambiguity       -> GLM max
    final email              -> benchmark-selected premium writer
    semantic QA              -> GLM Flash
    difficult QA             -> GLM high
    deterministic safety     -> CODE

**`deterministic safety -> CODE` is not a routing entry to be filled in later.**
Section 2: *LLMs reason. Code governs.* Suppression, sending eligibility,
activation, budgets, ceilings, schemas, identity, provenance, provider state,
cadence, approval and production writes are decided in Python. If the router is
ever asked to route one of those, it must **REFUSE**, not pick a model.

## The test that makes it stick

`tests/test_no_model_slug_lives_outside_the_policy.py` greps the tree for model
slugs outside the policy file and **fails on any hit.**

Known slugs present on master today, so the test has something real to catch:
`claude-sonnet-4-20250514`, `glm-4.6` / GLM model names in
`src/providers/glm.py`, whatever `xai.py` and `config.py` carry, and the
`DEFAULT_MODEL` style constants.

Three traps to handle explicitly, or the test is worthless:

1. **A slug in a comment or a docstring is not a violation.** Parse with `ast` and
   check string literals, not raw lines - this codebase has already shipped a test
   that failed when somebody wrote a comment.
2. **`tests/` legitimately names models** in fixtures and assertions. Exclude it,
   and say so.
3. **The policy file itself** is where slugs live. Exclude it by path, not by
   pattern.

## Acceptance - RUN each, paste real output

1. The router resolves, and its decision is data rather than a string:

    py -3 -c "import sys;sys.path.insert(0,'.');from src import modelrouter as R;\
    d=R.resolve('research_synthesis');\
    print(d);\
    assert d.provider and d.model and d.policy_version"

   Name your real API; the assertion is that provider, model and policy_version
   all come back.

2. **Routing a deterministic-safety task REFUSES:**

    py -3 -c "import sys;sys.path.insert(0,'.');from src import modelrouter as R;\
    ok=False;\
    exec('try:\n R.resolve(\'suppression\')\nexcept R.NotAModelDecision:\n ok=True');\
    assert ok,'the router picked a model for a deterministic safety decision';\
    print('refused correctly')"

3. **The slug test FAILS on a planted violation.** Add
   `MODEL = "claude-sonnet-4-20250514"` to a scratch module in `src/`, run the
   test, confirm it FAILS and NAMES the file and line, delete the scratch, confirm
   green. Confirm the plant actually landed. **Paste all three runs** - a guard
   never seen to fail is not known to work.

4. **A slug in a comment does NOT trip it.** Fixture proving it.

5. **Fallback resolves.** Assert that when the primary provider is marked
   unavailable the router returns the declared fallback, and that a policy entry
   with no fallback says so explicitly rather than returning None silently.

6. Full suite: wait for `work/suite_verdict.txt`, diff the failing-name SET
   against `docs/state/SUITE-BASELINE-2026-09-26.txt` (128 names).

## What this task may NOT do

- **Do not change which model any existing stage uses.** This task builds the
  router and moves the slugs into it. Re-routing is TASK-362's, after the policy
  exists. The directive says: *do not change production routing blindly; first
  understand what exists.*
- Do not route a deterministic gate.
- Do not make a live model call. Fixtures only.
- Nothing sent, nothing activated.
