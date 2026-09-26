PRIORITY: P0
SIZE: M
DEPENDS:

# TASK-330 — the anti-fabrication rule passes on a reused number

**SEVERITY: HIGH.** Buggie finding H3, `docs/BUGGIE-FINDINGS-2026-09-26.md`.

## The defect

`src/copylint.py:_traces(value, supported)` reduces to:

    token = _norm(value); return token in supported

`untraceable()` extracts each "specific" from a sentence — a number, date,
percentage or proper noun — and asks only whether that exact string appears
ANYWHERE in the lead's pack text. It never asks whether the specific supports the
claim it is now being used to make.

**Measured consequence:** a pack containing "raised $50M in 2019" makes the
fabricated sentence "grew revenue by $50M last quarter" pass as traceable,
because "$50M" appears verbatim in the pack.

`untraceable_company_claim` is a REFUSE rule. It is the anti-fabrication gate,
and it can be satisfied by coincidence. The fifty currently carries 4 leads
refused on this rule — the question this task answers is how many were *wrongly
allowed*.

This is exactly what `docs/OPERATOR-DIRECTIVES-2026-09-26-PHASE1.md` §9 forbids:
*"A message sharing the word 'marketing' with a research pack is not evidence
that the message is grounded in the research. Grounding validation must evaluate
whether the prospect-facing claim is actually supported by the underlying
evidence."*

## Build

    src/copylint.py    MODIFY. `_traces` must bind a specific to the CLAIM it
                       appears in, not to the document.
    tests/test_a_reused_number_does_not_launder_a_new_claim.py   NEW

A specific traces only when the pack sentence it came from supports the same
assertion. At minimum: carry the pack sentence that contained the specific, and
require the drafted sentence to be consistent with it. Where that cannot be
established deterministically, **REFUSE** — a fabrication that ships is far worse
than a true sentence that needs rewriting.

## The rule that governs the fix

**Deterministic gates stay authoritative.** Directives §9: *"Semantic validation
may add another layer, but an LLM score must never override deterministic
failures."* You may not resolve this by asking a model whether the claim is
grounded and letting a high score pass a sentence the deterministic check
refused.

Also `CLAUDE.md`: *"Never widen a lint rule to make a draft pass. Regenerate the
draft."* If the tightened rule refuses copy that used to pass, that is the rule
working.

## Acceptance — RUN each, paste real output

1. The laundering case REFUSES:

    py -3 -m unittest tests.test_a_reused_number_does_not_launder_a_new_claim -v

   must contain a test where the pack says one thing about a figure and the draft
   says another thing with the same figure, and the result is a REFUSAL naming
   the sentence.

2. **A genuinely supported claim still passes.** A tightened rule that refuses
   everything is not a fix. Include a case where the draft restates the pack
   sentence faithfully and assert it passes.

3. **The guard is seen to fail.** Revert your change, re-run, confirm the new test
   FAILS on the old code, and confirm the revert actually landed (`grep -c` the
   changed line). Paste both runs. A patch that silently no-ops produces a green
   run worth nothing.

4. Re-lint the fifty's existing copy and report the DELTA: how many of the 31
   written leads change verdict. The fifty currently has 15 copylint refusals;
   report the new number and name the newly-refused leads. **Do not modify the
   fifty's files** — they are posted and hashed.

5. Full suite: wait for `work/suite_verdict.txt`, diff the failing-name SET
   against the baseline, not the count.

## What this task may NOT do

- Do not widen any rule. Do not move a REFUSE to a warning.
- Do not call a model to decide groundedness (see above).
- Nothing sent, nothing activated, no provider call.
