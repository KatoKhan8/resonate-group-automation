PRIORITY: P1
SIZE: L
DEPENDS: TASK-360

# TASK-363 - the copy tournament on the fifty

**Operator scope 5, 2026-09-26**, and directive section 11. Sonnet's place as the
writer must become an evidence-based routing decision rather than architectural
dogma.

## The four arms, on the SAME facts and the SAME prompts

    A   Claude Sonnet          the current writer
    B   GLM high reasoning
    C   GLM Flash
    D   GPT-6 Sol

Same accounts, same context, same prompts. **The only variable is the model.** If
an arm needs a different prompt to work at all, that is a finding to report, not a
licence to change the prompt for one arm.

Run it on **the fifty** - the cohort is already produced, its facts are already
extracted and verified first-party, and its gate results are known (31 written, 16
copylint clean, 21 sequencegate passed, 13 through both).

## Blind, and blind means blind

- **The operator's pages must not reveal which arm produced which copy.** Label
  them by a shuffled key, and keep the mapping in a separate file the review page
  does not link to.
- Do not put the model name in the HTML, in a comment, in a filename, in a CSS
  class, or in the tab title. A reviewer who can guess the arm is not blind.
- Email and LinkedIn are **scored separately.** The directive is explicit, and
  they are different jobs: email carries the structured commercial argument,
  LinkedIn carries lighter context.

## Score these, per arm, per channel

specificity, factual grounding, naturalness, clarity, Productive explanation,
persona relevance, account relevance, offer clarity, CTA quality, follow-up
novelty, semantic repetition, fake specificity, hallucination,
Email/LinkedIn complementarity.

**Also run the existing gates on every arm and report the results** - copylint and
sequencegate pass rates per arm are the cheapest objective signal available, and
they are not a matter of taste. An arm that writes beautifully and fails
`unrendered_variable` is not a better writer.

## Deliverable

    docs/benchmarks/TOURNAMENT-2026-09-26/          NEW
      README.md               method, arms, what was held constant
      pages/<key>.html        blind pages for the operator
      mapping.json            key -> arm. NOT linked from the pages.
      scores.json             per arm, per channel, per criterion
      gates.json              copylint and sequencegate results per arm

Record the **`model_policy` version** used, per the operator. A benchmark whose
routing cannot be reproduced is not evidence.

## Cost, and the cap

The fifty cost $3.1464 for 31 written leads on Sonnet alone. Four arms over the
same cohort is roughly four times the generation, and three of the arms are
cheaper than Sonnet.

**Cap the whole tournament at $25 and report real spend per arm from the ledger.**
If an arm would exceed the cap, run it on a documented subset and say which leads
- a smaller honest sample beats a truncated run reported as complete.

GLM's resetting allowance is used before anything billed per token, so arms B and
C should cost close to nothing against it.

## Acceptance

1. All four arms generated on the same lead set, with the set named.
2. **The blind holds:** grep every file under `pages/` for each model name and
   assert zero hits. Paste the grep.
3. Email and LinkedIn scored separately, per criterion, per arm.
4. Gate results per arm: copylint and sequencegate pass rates, with the rules that
   fired.
5. Real spend per arm from the ledger, and the total against the $25 cap.
6. `model_policy` version recorded.
7. **No conclusion drawn.** Report the numbers. Choosing the writer is the
   operator's decision from the evidence, and the directive says not to choose
   from intuition.

## What this task may NOT do

- **Do not change the writer routing.** This produces evidence; the operator
  decides.
- Do not reveal the arms on the review pages.
- Do not modify the fifty's posted, hashed files
  (`0c493ab9c3d9d136` / `775cd55287b8f29a`).
- Do not exceed $25.
- Nothing sent, nothing activated. This is a benchmark, not a cohort.
