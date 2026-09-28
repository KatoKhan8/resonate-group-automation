PRIORITY: P1
SIZE: L
DEPENDS:

# TASK-429 — the workforce report, 2026-08-01 to now, from machine state only

**Operator request, Zvonimir, 2026-09-27.** Deliverable:
`docs/WORKFORCE-REPORT-2026-09-27.md`, plus a short Croatian summary posted to
`#resonate-os`.

This is an OFF-CRITICAL-PATH task and it belongs to the Qwen lane. It must not
touch `src/bisonfactory.py`, `src/heyreachfactory.py`, `src/generate.py`,
`src/sequenceplan.py` or `tests/test_generate.py` — Claude subagents are working
in those files. This task writes ONE new document and adds no production code.

## THE ONE RULE THAT DECIDES WHETHER THIS REPORT IS WORTH ANYTHING

**From machine state only. `UNKNOWN` wherever no source exists.**

Not from a handoff's prose, not from a task file's own claim about itself, not
from a result block's self-assessment, and not from an estimate. Every number in
this report names the source it was derived from. A cell you cannot source is
written `UNKNOWN` — it is never left blank, never interpolated, and never
softened into a plausible figure.

This matters more here than in most tasks, because a workforce report is
exactly the kind of document that gets believed later. Measured on 2026-09-26: of
13 tasks a handoff listed as "done and verified", three artifacts existed on no
ref at all. A report that counts those three as delivered is worse than no
report, because it is used to decide where work goes next.

**State is explicit, never inferred.** A task file's STAGE is an artifact, not
task state. A branch is not a merge. A commit's author is not necessarily the
worker that did the work — check how authorship is set in this repo before
relying on it, and if it cannot distinguish workers, say so and use a source
that can.

## PART 1 — PER WORKER

One row per worker: **Claude, Qwen, GLM, Grok, Groq, Sonnet.**

Columns:

    tasks delivered
    accepted first pass
    reworks
    defects introduced
    defects found
    hours to fix
    tokens
    cost

For each column, state in the document HOW it was derived and from WHICH files.
Candidate sources, to be verified rather than assumed: the task files under
`docs/qwen-tasks/` and their result blocks, `docs/state/LEDGER.json` and
`docs/state/QUEUE-MANIFEST.json` (both DERIVED — regenerate with
`scripts/durable_state.py` rather than trusting the committed copy),
`scripts/task_registry.py`, `docs/glm-reviews/`, the git history, and the spend
ledger written through `enrich.spend()`.

Where a column has no machine source for a given worker, the cell is `UNKNOWN`
and the report says what would have to exist to fill it. That list is itself a
useful result: it says what this project cannot currently measure about its own
workforce.

"Defects introduced" and "defects found" both need a definition stated in the
document before the numbers appear, and the definition must be one a reader can
apply to a specific task and get the same answer. If the evidence only supports
a weaker claim — for example "reworks requested" rather than "defects
introduced" — report the weaker claim under its own honest name.

## PART 2 — THE PROVIDER SPLIT, AND WHY IT IS TWO TABLES

The two halves answer different questions and averaging them produces a number
that means nothing.

**FIXED SUBSCRIPTIONS** — Claude Max, Qwen, GLM / Z.ai, Apify Scale.
Report **plan utilisation** and **cost per accepted task**. The marginal cost of
one more task on a fixed plan is zero until the plan is exhausted, so the
question is how much of the allowance was actually used for useful eligible work.
Per the model policy: use resetting capacity preferentially, but **never create
work to consume capacity** — so low utilisation is not automatically a finding,
and the report must not imply it is.

**PAY-PER-USE** — Groq, Anthropic API, OpenRouter, CheapVerifier, Reoon,
Deliverable, ContactOut, AI-ARK.
Report **ledger spend**. The authority is the internal waterfall ledger written
by `enrich.spend()`, not a provider dashboard and not a nightly usage job —
`TASK-359` is deferred until the ledger is proven, so only the ledger-based cost
view is in scope here. A provider call that skipped `spend()` is invisible to
the ledger; if you find evidence of such calls, report that as a finding rather
than silently under-reporting the total.

Never print a credential value. Reference an environment variable by NAME only,
and take names from `config.VARIABLES` rather than guessing one — four plausible
but invented names once produced a report concluding that four working providers
were unauthenticated.

## PART 3 — THE CROATIAN SUMMARY

Short, in `#resonate-os`, owner language. No line numbers, no function names, no
SHAs, no test framework detail. Say what the workforce actually delivered, what
it cost, and the one or two things the numbers say that were not already
obvious. If the honest headline is "we cannot measure X", that is the headline.

## ACCEPTANCE

1. `docs/WORKFORCE-REPORT-2026-09-27.md` exists, is committed and is pushed, and
   every number in it names its source.
2. Every unsourceable cell reads `UNKNOWN`, and the report lists what would have
   to exist to fill each one.
3. The two provider tables are separate, with utilisation and cost-per-accepted-
   task on the fixed side and ledger spend on the pay-per-use side.
4. Pick any three numbers in the report at random and re-derive them from the
   named source. All three reproduce. Record that check in the result block,
   naming which three.
5. The Croatian summary is posted.
6. Provider writes = 0. No provider is called to build this report except a read
   that already exists in the codebase; no new provider integration is written.

## RESULT

STATUS: DONE
COMMIT SHA: 89ca42f6
TESTS: N/A — document-only task, no code changed.
FILES CHANGED:
  docs/WORKFORCE-REPORT-2026-09-27.md  (new) — the workforce report

FINDINGS:

  1. THE REPO WAS CREATED 2026-09-09. The report period 2026-08-01 to
     2026-09-08 has zero machine state. All 1,814 commits fall in
     2026-09-09 to 2026-09-27.

  2. PER-WORKER ATTRIBUTION IS STRUCTURALLY IMPOSSIBLE from current state.
     Three independent checks confirm this:
     - Git author: all commits are "Zvonimir Beslic" or "c" (merge bot).
     - Task registry: `worker` field is null for all 255 DONE tasks.
     - Task files: no RESULT block has a WORKER: field.
     The per-worker table in the report is entirely UNKNOWN except for
     GLM tokens (31,227 from 4 branch-verification files in docs/glm-reviews/).

  3. 268 tasks in DONE, 19 in REVIEW, 4 in REWORK, 3 in BLOCKED, 177 in TODO.
     236 of 268 DONE files have RESULT blocks; 32 do not. 80 have COMMIT SHA.

  4. THE SPEND LEDGER IS NOT ACCESSIBLE from this worktree. It lives at
     work/spend-ledger.jsonl (gitignored, Claude's worktree only). All
     pay-per-use provider spend cells are UNKNOWN.

  5. NO SUBSCRIPTION COST DATA exists in any committed file. Fixed-subscription
     utilisation and cost-per-accepted-task are UNKNOWN.

  6. CROATIAN SUMMARY is written in Part 3 of the report but NOT posted to
     #resonate-os — no Slack access from this worktree. Operator must post.

  7. VERIFICATION CHECK: Three numbers re-derived from named sources:
     - Tasks in DONE = 268 (ls docs/qwen-tasks/DONE/*.md | wc -l → 268)
     - GLM token total = 31,227 (8061+5976+6854+10336 from 4 branch-*.md files)
     - Remote branches = 372 (git branch -r | wc -l → 372)
     All three reproduce.

RISKS:
  - The report's headline finding is that the project cannot measure its own
    workforce. This is the honest answer from machine state. If the operator
    expected per-worker breakdowns, the gap is in the measurement infrastructure,
    not in the report.
  - The Croatian summary is written but not posted. Acceptance criterion 5 is
    not fully met.

RECOMMENDED CLAUDE ACTION:
  - Review the report, especially the UNKNOWN cells and the "what would have to
    exist" sections. If per-worker attribution is a priority, the fix is a
    WORKER: field in the RESULT block template and a durable claim log.
  - Post the Croatian summary to #resonate-os manually.
  - If the spend ledger should be committed (redacted), that is a separate task.
