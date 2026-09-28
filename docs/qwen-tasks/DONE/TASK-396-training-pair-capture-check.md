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

## RESULT

**Artifact kind:** finding (read-only investigation, no code changed)

STATUS: DONE
COMMIT SHA: 723dad87
TESTS: N/A — no code changed; nothing to verify
FILES CHANGED: this task file only

### FINDINGS

**Nothing captures a training pair. Zero modules, zero files, zero references.**

Exhaustive trace across `src/`, `tests/`, `docs/`, and all `.py` files:

| Search term | Hits in src/ | Hits in tests/ | Verdict |
|---|---|---|---|
| `training_pair` | 0 | 0 | nothing |
| `training` | 0 | 1 (substring of "constraining" in a comment) | nothing |
| `fine.?tun`, `rlhf`, `dpo`, `sft`, `reinforcement.*learn` | 0 | 0 | nothing |
| `preference_pair`, `feedback_pair`, `train_pair` | 0 | 0 | nothing |
| `prompt.*completion`, `input.*output.*pair`, `model.*output.*human` | 4 (all `prompt_tokens`/`completion_tokens` in llm.py/modelprices.py — usage billing, not pair capture) | 0 | nothing |
| `capture.*prompt`, `store.*prompt`, `save.*prompt`, `record.*prompt` | 7 (all about prompt *assembly* for generation, not persistence of prompt+output pairs) | 0 | nothing |
| `human.*verdict`, `human.*judg`, `human.*label` | 3 (`qualify.py:212` records a human decision on an ICP verdict; `dmplan.py:272` and `web/api.py:1835` read it) | — | ICP verdict layer only, not linked to model output |

**What the codebase DOES have (none of which is a training pair):**

1. **Approval workflow** (`src/approve.py`, `src/approval.py`): a human approves or rejects generated *draft text* per contact per step. The fingerprint (`approval.fingerprint`) tracks whether the approved words have changed. But the **prompt that produced the draft is not stored** — `llm.py:208` states explicitly: *"The raw payload carries the prompt back and is not stored anywhere."*

2. **ICP human verdict** (`src/qualify.py:212` — `record_human_decision`): a human reviews a company's ICP classification. This is a verdict on a *company qualification*, not on a model-generated output. No prompt or model output is captured alongside it.

3. **QA layer** (`src/qa.py`): checks for duplicate subjects/bodies, coherence, lint. The word "pair" appears only in `duplicate_pairs` — pairs of steps with identical copy. No model prompt or output is captured.

4. **LLM usage logging** (`src/llm.py:951` — `USAGE_FIELDS_RECORDED`): records `prompt_tokens`, `completion_tokens`, `total_tokens`, `seconds`, `chars` — billing metrics, not the prompt text or the model's output text.

5. **Variant evaluation** (`src/variants.py`, `src/outcomes.py`): evaluates which copy variant performed better by reply rate. This is an outcome comparison, not a prompt→output→verdict pair.

**The gap, stated plainly:** When `generate.py` calls the model to draft an email, the prompt is assembled, sent to the LLM, the response is parsed and linted, and the approved text is stored on the record. The prompt itself is discarded (`llm.py:208`). When a human later approves or rejects the draft, that verdict is recorded as a fingerprint match/mismatch — but there is no stored prompt to pair it with, and no stored raw model output either. The three elements (prompt, output, verdict) that would form a training pair exist transiently and are never persisted together.

### RISKS

- None. This is a read-only finding. No code was changed.

### RECOMMENDED CLAUDE ACTION

- Acknowledge the finding: no training pair capture exists. This is genuinely not built yet.
- If/when training pair capture is wanted, the natural insertion point is `generate.py` (where the prompt is assembled and the model response is received) plus `approve.py` (where the human verdict lands). The missing link is persisting the prompt+output at generation time and linking the approval verdict back to that stored pair.
- No action required from this task.
