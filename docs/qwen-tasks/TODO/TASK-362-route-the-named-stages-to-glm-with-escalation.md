PRIORITY: P1
SIZE: L
DEPENDS: TASK-360

# TASK-362 - route the named stages to GLM, with escalation

**Operator scope 3 and 4, 2026-09-26.** GLM capacity is at roughly 1% of both the
5-hour and weekly limits, so it is to be used aggressively where it makes the
system smarter - **not** rationed, and **not** spent on meaningless tokens.

## Route to GLM now, and only these

    Second Brain extraction and synthesis
    fact normalisation
    signal relevance
    person relevance
    semantic repetition checks
    grounding checks
    reply classification
    objection extraction
    referral extraction
    first-pass verification of every finished branch   (TASK-345 owns the harness)

**Groq keeps trivial classification.** **Claude Sonnet stays the writer** until
the tournament (TASK-363) says otherwise. **Deterministic gates stay final
authority** - a deterministic FAIL remains FAIL, and no GLM verdict may overturn
one. Section 5 of the directive says so in as many words.

## Escalation, in the router rather than in each caller

    cheap pass, confident              -> accept
    low confidence or conflict         -> escalate to GLM high
    still ambiguous                    -> OPERATOR QUESTION

**Never max reasoning for trivial extraction.** Section 13: do not use max
reasoning to extract a company name, and do not send a 100K-token Second Brain
where task-specific retrieval needs 8K.

The third rung is the one that is easy to get wrong: *still ambiguous* must become
**a question for the operator**, not a third model call that picks something. An
escalation ladder whose last rung is "decide anyway" is not an escalation ladder.

## Every routed stage must name its production consumer

The directive is explicit: *"Do not create another disconnected architecture
document that nobody consumes. Any model-routing design must identify the
production caller/consumer."*

So for each of the ten stages above, state in your result block **which module
calls it in production.** Several currently have none - `secondbrain.for_task` had
zero callers, `copystages` and `sequencegate` still do. **Routing a stage nothing
calls achieves nothing**, so where the consumer does not exist, say so and mark
that stage ROUTED-BUT-UNCONSUMED rather than reporting it as done.

## Acceptance - RUN each, paste real output

1. Each of the ten stages resolves to the intended provider and reasoning level
   through the router. Print the table.
2. **Escalation is observed, not asserted:** a fixture returning low confidence
   escalates to GLM high; a fixture that is still ambiguous produces an operator
   question. Assert the third rung does NOT return a model answer.
3. **A deterministic FAIL survives a GLM PASS.** Construct the case: deterministic
   gate fails, GLM says the copy is fine, assert the overall result is REFUSED.
   **This is the assertion that closes the task.**
4. **Trivial extraction does not get max reasoning:** assert the reasoning level
   for a simple extraction task is the cheap tier.
5. Per-stage production consumer named, or marked ROUTED-BUT-UNCONSUMED.
6. Observability: every call writes a row carrying `task_type`, `model`,
   `reasoning_level` and `policy_version` (TASK-361).
7. Full suite: wait for `work/suite_verdict.txt`, diff the failing-name SET.

## Budget

GLM's resetting allowance is to be used before anything billed per token, so
fixture and dry-run work here is cheap by design. **Cap live GLM calls in this
task at 200** and report the count and the token totals from the ledger. Do not
call Sonnet at all.

## What this task may NOT do

- Do not re-route the writer. Sonnet keeps final copy until TASK-363's evidence.
- Do not let a GLM verdict override a deterministic gate.
- Do not route suppression, eligibility, activation, budgets, schemas, identity,
  provenance, provider state, cadence or approval. Those are CODE.
- Nothing sent, nothing activated.
