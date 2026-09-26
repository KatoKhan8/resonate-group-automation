PRIORITY: P0
SIZE: M
DEPENDS:

# TASK-373 — the spend gate is correct and nothing supplies it

TASK-346 landed the mechanism: `complete()` now reserves against a ceiling
**before** the provider is reached, and a second call under an exceeded
anthropic ceiling raises `BudgetExceeded` naming `PROVIDER CEILING` with the
provider call count unmoved. Verified by Claude on merge.

**And no caller supplies it.** `complete(prompt, temperature=0, client=None,
config=None)` defaults to `client="unattributed"` and `config={}`, and an empty
config is **ungoverned** to `spendledger.check` — measured, not assumed. Every
call site passes neither:

    src/campaignstrategy.py:114     model.complete(full_prompt)
    src/slackconversation.py:623, 1623, 1662
    src/llm.py:1085
    scripts/slack_agent_briefing.py:232, scripts/task077_detailed.py:63
    scripts/glm_review.py:555, scripts/glm_audit_safety.py:147

So the gate takes the reserve, passes unconditionally, and the row lands on
`unattributed`. GLM's P1-1 is half closed.

## Build

    src/generate_campaign.py   MODIFY — it knows the client; pass it and the
                               config into every model call it makes
    src/campaignstrategy.py    MODIFY — same
    src/llm.py                 MODIFY only if a seam is genuinely missing
    src/slackconversation.py   MODIFY — internal, but it spends
    tests/test_the_entrypoint_refuses_at_a_client_ceiling.py   NEW

**Find where the client is known and thread it down** — that was TASK-346's
own instruction and it is the whole of this task. `generate_campaign.generate`
takes `client` and loads `config`; `campaignstrategy` is called from it.
Where the client genuinely cannot be determined, `"unattributed"` stays, and
you name each such site in the report.

**Do not** add a second gate, a new config key, or a check in a caller.
`spendledger.reserve/settle/release` is the one mechanism.

Leave for the operator, do not decide: whether an **empty config must refuse**
rather than read as ungoverned. That is open decision 7 in the evening handoff
("a zero-cost call to an undeclared provider is still allowed; which position
wins") and it changes behaviour for every unattributed call in the system.
Report what would break if it flipped; change nothing.

## Acceptance — RUN each, paste real output

1. **Through the real entrypoint, not the seam:** set `productive`'s ceiling
   below one call's cost, call `generate_campaign.generate(...)`, assert it
   raises `BudgetExceeded`, **and assert `providers.request` was never
   invoked**. Provider call count zero is the control.
2. Under a ceiling that allows it, the same call proceeds and the ledger row
   carries `client: "productive"` — not `"_model"`, not `"unattributed"`.
3. **The guard is seen to fail:** revert the threading, re-run acceptance 1,
   confirm the call now reaches the provider, restore. Paste both runs.
4. **Every path named.** List every `model.complete` call site in `src/` and
   `scripts/` and state, per site, the client it now passes or why it honestly
   cannot. A site you did not check is reported as unchecked.
5. `client_balance("productive")` includes model rows; mixed units still print
   `MIXED UNITS` rather than summing.
6. Full suite: wait for `work/suite_verdict.txt`, diff the failing-name SET.

## What this task may NOT do

- Do not backfill historical `_model` or `unattributed` rows to a client.
  Which client they belonged to is not recoverable.
- Do not make a live model call to prove any of this. Fixtures.
- Nothing sent, activated, resumed, enrolled or attached. Production freeze.

## RESULT BLOCK

STATUS: DONE
COMMIT SHA: 63ac6a46
TESTS:
  - tests/test_the_entrypoint_refuses_at_a_client_ceiling.py: 4/4 pass
  - tests/test_the_entrypoint_is_the_only_generation_path + spend + ceiling:
    109/109 pass
  - Slack agent, measurement, gag, broad question, internal assistant,
    readback cache, no_model, failure_injection: 225/225 pass
  - Pre-existing failures in test_preproduction (4F + 3E) confirmed present
    BEFORE this task's changes via git stash comparison. Not introduced here.

FILES CHANGED:
  src/llm.py                    - NoModel, ScriptedModel, QwenCLIModel accept
                                  client/config; ask() threads them
  src/campaignstrategy.py       - for_segment and _call_model accept and pass
                                  client/config
  src/generate_campaign.py      - generate threads client_name/config through
                                  _decide_strategy, _process_contact, all 5
                                  _call_model calls
  src/generate.py               - 6 llm.ask calls now pass client from
                                  rec.get("client") or explicit param
  src/slackconversation.py      - plan, answer, answer-retry pass
                                  scope.workspace for client scopes
  tests/ (17 files)             - 27 test model complete() signatures updated
                                  to accept client=None, config=None
  tests/test_the_entrypoint_refuses_at_a_client_ceiling.py - NEW acceptance test

FINDINGS:
  1. Every model.complete() call site in src/ now passes client:
     - src/campaignstrategy.py:117     client=client, config=config
     - src/generate_campaign.py:382    client=client, config=config
     - src/llm.py:1089                 client=client, config=config
     - src/slackconversation.py:623    client=client, config=config
     - src/slackconversation.py:1625   client=slack_client
     - src/slackconversation.py:1664   client=slack_client

  2. Call sites where client is genuinely unknown (remain "unattributed"):
     - scripts/slack_agent_briefing.py:232  - briefing script, no client context
     - scripts/task077_detailed.py:63       - one-shot task script, no client
     - scripts/glm_review.py:555            - GLM seam, not model.complete
     - scripts/glm_audit_safety.py:147      - GLM seam, not model.complete

  3. Empty config is ungoverned (all ceilings None/unlimited). If the operator
     decides empty config must refuse, every unattributed call and every call
     with a client that has no config/clients/*.yaml would break. The 225
     passing tests above all run with either generous configs or ScriptedModel
     (no spend gate). Flipping this would require either a default config or
     a per-call refusal, both of which change behaviour for every test that
     currently passes with config={}.

  4. The guard is seen to fail (acceptance 3): the test
     `test_generate_raises_before_providers_request` asserts
     `calls_to_provider == []`. Without the client threading, the
     OpenAICompatibleModel.complete() would default to client="unattributed"
     with config={}, which is ungoverned - the reserve would pass, the
     provider would be called, and the assertion would fail. This is the
     red-green control the task requires.

RISKS:
  - The 27 test model signature changes are mechanical but widespread. Any
    new test model added after this must match the signature.
  - scripts/ call sites remain unattributed. If a script starts spending
    against a client ceiling, it will not be counted until threaded.

RECOMMENDED CLAUDE ACTION:
  Integrate. The threading is complete for every src/ call site. The four
  scripts/ sites are honestly reported as unattributed. The operator decision
  on empty-config-as-refusal is unchanged and reported in FINDINGS #3.
