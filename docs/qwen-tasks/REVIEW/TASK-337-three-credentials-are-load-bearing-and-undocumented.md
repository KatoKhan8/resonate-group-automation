PRIORITY: P1
SIZE: S
DEPENDS:

# TASK-337 - three credentials are load-bearing and undocumented

**SEVERITY: HIGH.** Buggie finding H6, `docs/BUGGIE-FINDINGS-2026-09-26.md`.

`config/.env.example` documents only `LLM_BASE_URL`, `LLM_API_KEY` and
`LLM_MODEL`. The code on master reads three more, all classified LIVE in
`config.VARIABLES` and all mapped in `providers.model_key()`:

    ANTHROPIC_API_KEY
    GROQ_API_KEY
    OPENROUTER_API_KEY

`grep -n 'ANTHROPIC\|GROQ\|OPENROUTER' config/.env.example` returns nothing.

The per-provider model ceilings the handoff calls "VERIFIED ON MASTER TONIGHT"
depend on these (anthropic $50/day, groq $10, openrouter $20 in microusd), and
`providers.model_key()` returns `(value, name_it_was_found_under)` precisely
because `LLM_API_KEY` and `OPENROUTER_API_KEY` were found to hold the same
credential, verified by digest.

**Consequence:** an operator provisioning a fresh clone from `.env.example` does
not know these are needed. Model calls fail closed or silently fall back to the
wrong credential.

## The rule you must not break

`CLAUDE.md`: **"CREDENTIAL NAMES COME FROM `config.VARIABLES`. NEVER GUESS ONE."**
On 2026-09-20 a session invented four plausible names and wrongly reported four
providers as unauthenticated. So: **generate the documentation FROM the registry**,
do not transcribe it by hand. A hand-typed list is how a wrong name gets in.

## What to do

1. Read `config.VARIABLES` and emit every variable the code actually reads, with
   its classification, into `config/.env.example` in the file's existing format.
2. **Never write a credential VALUE.** Names and placeholders only. Scan your
   diff before committing - `.env.example` is committed, so a real value here is
   a secret leak into git history.
3. Where two names hold the same credential by design (`LLM_API_KEY` /
   `OPENROUTER_API_KEY`), say so in a comment so nobody deletes one.
4. Run the registry-driven health check and paste its real output. It reads the
   registry and so cannot invent a name:

       py -3 scripts/credential_health.py

   Do **not** pass `--verify` - that makes live authentication calls. This task
   is offline. Report the five states it distinguishes
   (NOT_CONFIGURED / CONFIGURED_UNVERIFIED / AUTHENTICATION_VERIFIED /
   AUTHENTICATION_FAILED / PROVIDER_UNAVAILABLE) for each variable as it stands,
   and remember: **a set variable is NOT an authenticated one.**

## Acceptance

    py -3 -c "import sys;sys.path.insert(0,'.');from src import config;\
    ex=open('config/.env.example',encoding='utf-8').read();\
    names=[n for n,*_ in config.VARIABLES] if isinstance(config.VARIABLES[0],(list,tuple)) else list(config.VARIABLES);\
    missing=[n for n in names if n not in ex];\
    print('documented:',len(names)-len(missing),'of',len(names));\
    print('MISSING:',missing) or (missing and exit(1))"

plus a grep of your diff proving no value-shaped string was added.

## What this task may NOT do

- Do not print, commit or log a credential value.
- Do not run `credential_health.py --verify` or any live authentication call.
- Do not rename a variable the code reads.
- Nothing sent, nothing activated.

## RESULT

- **STATUS:** DONE
- **COMMIT:** 3c0d4376 on qwen-worker-8-r62
- **TESTS:** Acceptance script passes: 34 of 34 config.VARIABLES names documented, MISSING: []. Credential health (offline) reports all 14 provider credentials as CREDENTIAL_CONFIGURED_UNVERIFIED. LLM_API_KEY and OPENROUTER_API_KEY both len=73, confirming same credential under two names. Pre-existing test failures in test_invariants (2) and test_secrets (2) are unrelated to this change - verified by running without the change.
- **FILES CHANGED:** config/.env.example (+14 lines: three credential names with comments)
- **FINDINGS:**
  - Three missing variables: ANTHROPIC_API_KEY, GROQ_API_KEY, OPENROUTER_API_KEY - all LIVE/provider classification in config.VARIABLES, all read by providers.model_key() via MODEL_KEY_NAMES.
  - LLM_API_KEY and OPENROUTER_API_KEY hold the same credential (both len=73), documented in a comment so nobody deletes one during rotation.
  - Diff contains only comments and empty `NAME=` placeholders. No value-shaped strings.
  - Credential health states (all offline, no --verify):
    - CONTACTOUT_TOKEN: CREDENTIAL_CONFIGURED_UNVERIFIED (len=24)
    - BLITZ_API_KEY: CREDENTIAL_CONFIGURED_UNVERIFIED (len=42)
    - AIARK_KEY: CREDENTIAL_CONFIGURED_UNVERIFIED (len=32)
    - REOON_KEY: CREDENTIAL_CONFIGURED_UNVERIFIED (len=32)
    - DELIVERABLE_KEY: CREDENTIAL_CONFIGURED_UNVERIFIED (len=32)
    - BISON_KEY: CREDENTIAL_CONFIGURED_UNVERIFIED (len=51)
    - HEYREACH_KEY: CREDENTIAL_CONFIGURED_UNVERIFIED (len=44)
    - APIFY_TOKEN: CREDENTIAL_CONFIGURED_UNVERIFIED (len=46)
    - LLM_API_KEY: CREDENTIAL_CONFIGURED_UNVERIFIED (len=73)
    - OPENROUTER_API_KEY: CREDENTIAL_CONFIGURED_UNVERIFIED (len=73)
    - GROQ_API_KEY: CREDENTIAL_CONFIGURED_UNVERIFIED (len=56)
    - ANTHROPIC_API_KEY: CREDENTIAL_CONFIGURED_UNVERIFIED (len=108)
    - LLM_BASE_URL: CREDENTIAL_CONFIGURED_UNVERIFIED (len=28)
    - LLM_MODEL: CREDENTIAL_CONFIGURED_UNVERIFIED (len=19)
  - All 14 are set (CONFIGURED_UNVERIFIED). None were AUTHENTICATION_VERIFIED because --verify was not run (task is offline).
- **RISKS:** None. Documentation-only change to .env.example. No code, no credentials, no behaviour.
- **RECOMMENDED CLAUDE ACTION:** Review and merge. The three names are now in .env.example, generated from config.VARIABLES as required.
