# TASK-942 — the writer must be told how long its answer may be

## Why

`generate_campaign` asked the model for five emails, five LinkedIn notes, three
subjects and two P.S. lines and sent **no output cap at all**. The answer was
then truncated by the endpoint and the truncation was indistinguishable, to the
caller, from a model that had simply written invalid JSON — both arrived as a bare
`ValueError` and both were swallowed into an anonymous `error` hold.

Measured: of 48 reconstructed complete payloads the richest was **795 tokens**
(`waynemedia-com`), the median 709, and the observed cut landed at roughly **680
tokens — BELOW the median**. So the defect was the ABSENCE OF A LIMIT, not long
answers, and the fix is a budget derived from the ceilings `lint` already
enforces rather than a round number somebody liked.

## Scope

`src/generate_campaign.py`, `src/llm.py` and their tests. No change to
`src/eligibility.py` or `src/providerwrites.py`, no lint threshold moved, no gate
weakened.

## Acceptance

```
python -c "import sys; sys.path.insert(0,'.'); from src import generate_campaign as g; assert isinstance(g.WRITER_MAX_TOKENS, int), type(g.WRITER_MAX_TOKENS); assert g.WRITER_MAX_TOKENS == 1759, g.WRITER_MAX_TOKENS; print('OK the writer carries a budget:', g.WRITER_MAX_TOKENS, 'tokens')"
python -c "import sys; sys.path.insert(0,'.'); import importlib; from src import lint; import src.generate_campaign as g; before = g.WRITER_MAX_TOKENS; lint.MAX_WORDS = lint.MAX_WORDS * 2; importlib.reload(g); assert g.WRITER_MAX_TOKENS > before, (before, g.WRITER_MAX_TOKENS); print('OK the budget is DERIVED from lint, not a literal:', before, '->', g.WRITER_MAX_TOKENS)"
python -c "import sys; sys.path.insert(0,'.'); from src import llm; assert issubclass(llm.TruncatedAnswer, ValueError); assert issubclass(llm.UnusableAnswer, ValueError); assert issubclass(llm.TruncatedAnswer, llm.UnreadableAnswer); assert llm.TruncatedAnswer is not llm.UnusableAnswer; print('OK two named refusals, and an existing except ValueError still catches both')"
python -m unittest tests.test_the_writer_is_told_how_long_its_answer_may_be
```

### NEGATIVE CONTROL, and why each command can fail

- Command 1 fails if the budget is removed: `AttributeError` or a different number.
- **Command 2 is the one that matters.** It fails if the figure is a literal: a
  hand-written 1759 does not move when `lint.MAX_WORDS` doubles. Measured on this
  branch: 1759 → 2884.
- Command 3 fails if the two refusals collapse into one class, or if either stops
  being a `ValueError` — which would silently change what every existing
  `except ValueError` in the pipeline catches.
- Command 4 is the one that proves the classification does not read error text.
  `json.loads` reports **"Unterminated string starting at"** for the truncated
  input and **"Expecting ',' delimiter"** for the balanced-but-invalid one, and a
  real canary truncation produced that SECOND message — so a classifier reading
  the text would get it backwards. Balanced braces mean the model stopped where it
  meant to, which is `unusable`, and that is decided by structure.

### Mutation

Remove the `max_tokens=WRITER_MAX_TOKENS` argument from the writer call and
`tests/test_the_writer_is_told_how_long_its_answer_may_be.py` must go red at
`test_the_writer_call_carries_the_budget` with `None != 1759`, and at
`test_every_retry_carries_it_too`. Remove the classification and 8 of 30 go red —
but **not** `..._is_named_unusable`, which stays green, so the mutation is caught
by the DIFFERENCE disappearing rather than by the parser breaking.

## Files

`src/generate_campaign.py`, `src/llm.py`,
`tests/test_the_writer_is_told_how_long_its_answer_may_be.py`. The budget is read
from `lint`'s ceilings; it must not become a second copy of any number `lint`
already owns.
