PRIORITY: P2
SIZE: S
DEPENDS:

# TASK-396 — does anything capture a training pair (prompt, output, verdict)?

**Trace first.** Grep for "training", "training_pair", or any module that
pairs a model's prompt+output with a later human/QA verdict (approved,
rejected, held). If nothing exists, report that plainly — this may be
genuinely not built yet, which is a valid, complete answer, not a defect
to invent a fix for.

## If something exists but is incomplete

Name exactly what is captured and what is missing (e.g., prompt captured,
verdict never linked back). Build only the smallest missing link, with a
test proving one full pair (prompt → output → verdict) is retrievable
together after your change.

## Acceptance

1. Honest state of what exists today, file:line or "nothing found."
2. If you build something: one real pair round-tripped and read back whole.
3. Full suite: wait for `work/suite_verdict.txt`, diff the failing-name SET.

## What this task may NOT do

- Do not invent a training pipeline or a model fine-tuning plan - this is a
  data-capture check only.
- No live model call required; a fixture is sufficient.
