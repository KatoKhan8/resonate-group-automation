# Weekly OSS survey — 2026-10-16

Standing survey, set up 2026-09-23, run under a one-hour time box. Four
candidates were checked against this repository's code, not against their
own marketing. **No Qwen task is written this week.** Every candidate either
turned out to be a deliberate tradeoff this codebase already made, a
duplicate of a task already queued, or a dependency whose gain cannot be
measured without `work/`, which this session does not have. An empty queue
is the honest result of checking rather than assuming, and padding it with a
task nobody needs would be the exact failure this exercise exists to catch.

## 0. Premises checked, and what survived

| # | The premise going in | What the code actually shows |
|---|---|---|
| 1 | "Talon-style ML signature detection would catch more than our regex stripper" | True in principle, but `src/replies.py:1075-1089` already chose the opposite tradeoff **on purpose** — a signature without a `-- `/`___` delimiter is left in place because "a missed signature is safer than a clipped reply." Adopting Talon's approach means reopening a decision the code already documents, not filling a gap. |
| 2 | "DSPy's assertion/backtrack loop would fix the writer's stale-retry-reason problem" | The problem is real, but it already has an owner: `docs/qwen-tasks/TODO/TASK-977-...md`, Defect B, open today, names the exact same defect in `src/generate_campaign.py` (nine of ten retry reasons are stale) and prescribes fixing it in our own code. DSPy would be a new dependency solving a problem we have already scoped without one. |
| 3 | "Nango's unified-connector model would collapse the Bison/HeyReach duplication" | The duplication is real and already queued: `docs/qwen-tasks/TODO/TASK-273-a-conformance-suite-for-two-adapters-that-share-no-interface.md`, still TODO, documents the same asymmetry (no shared Protocol, `set_sequence` has different signatures, `tests/fakebison.py` exists and `fakeheyreach.py` still does not — reconfirmed this run). A second task on top of an unstarted one would not change what gets built, only who's asked to build it. |
| 4 | "Guardrails AI's schema-validator framework is a better fit than our hand-rolled lint" | Checked `src/lint.py:303-417` (`BANNED_PHRASES`, `explain`), `:648-694` (`check`, word-count contract), `:577-624` (`_names_match` greeting check). This is not a generic "does the output look like JSON/contain PII" validator — it enforces a specific, two-authority word-count equality (CLAUDE.md, TASK-943) and a banned-phrase list tuned against this estate's own refusal history. Guardrails would sit *beside* this logic, not replace it, for the cost of a new dependency. |

None of the four premises survived as "adopt this." All four survived as
"here is a real idea, and here is why it either duplicates existing work or
costs more than it is worth to measure without live data."

---

## 1. Talon (mailgun/talon) — email reply/signature parsing

**What it is.** A Python library, originally built at Mailgun, that strips
quoted thread content and signature blocks from email replies, using a mix
of heuristics and a trained classifier for the signature boundary.

**License.** Apache-2.0, confirmed via a third-party Maven listing and a PHP
port's README (`actengage/talon`) stating it is a port of `mailgun/talon`
under Apache-2.0. I could not confirm from search results alone whether the
upstream `mailgun/talon` GitHub repo is still actively maintained in 2026 —
flagging that rather than asserting it.

**What it does better than us, concretely.** `src/replies.py:1046-1089`
(`_find_quote_start`, `_strip_signature`) is regex-only: quote boundaries via
an Outlook separator, an "On ... wrote:" header, or a leading `>`; signature
boundaries via a literal `-- ` or `___` line. Talon's signature detection is
trained on a larger, more varied corpus and would catch signature blocks that
carry no delimiter at all (a plain name-and-title block, for instance).

**What it would mean here.** `src/replies.py:1075` already states the
counter-argument in its own docstring: catching more signatures risks
clipping genuine reply content, and the code chose to under-strip rather than
over-strip. Before touching this, the real question is **how often** the
current stripper misses a real signature in live traffic —
`UNVERIFIED (needs work/): a sample of inbound reply bodies from
work/queue.jsonl's confirmed-touch history, hand-checked against
_strip_signature's output, to measure a miss rate`. Without that number,
swapping in Talon's approach (as a dependency, or as a reimplemented
heuristic in our own words) is a guess about a problem whose size nobody has
measured. **Not proposed as a task this week** for exactly that reason.

---

## 2. DSPy (stanfordnlp/dspy) — typed prompt programs with metric-guided optimization

**What it is.** A framework from Stanford NLP for building LLM pipelines as
typed "signatures" and modules rather than hand-written prompt strings, with
optimizers (`BootstrapFewShot`, `MIPROv2`, `GEPA`) that search for
instructions and few-shot examples against a scoring metric, plus an
assertion/suggestion mechanism (`dspy.Assert`/`dspy.Suggest`) that retries a
module only against the constraints it is currently failing.

**License.** MIT, at `stanfordnlp/dspy`.

**What it does better than us, concretely.** `src/generate_campaign.py`'s
`MAX_WRITER_ATTEMPTS` loop (10 calls: 1 draft + 9 retries, raised 3→6→10 in
`b946b59c`) retries by handing the model the **full accumulated list** of
every reason any attempt has ever been refused for, not just the reasons the
*current* draft still offends. `docs/qwen-tasks/TODO/TASK-977-...md` Defect B
already measured this exactly: retry 9 is told nine stale complaints and one
live one. DSPy's assertion backtracking is built to solve precisely this
shape of problem — retry against the current failing checks only, with the
option to keep accumulating ones that are still live.

**What it would mean here.** This is a genuine idea, but it does not need
DSPy: TASK-977 already specifies the fix in our own retry loop (prune the
ledger to what the current draft actually offends, while still requiring
"satisfy every live constraint at once"), with an acceptance test that
distinguishes a re-offending draft from a cleanly-fixed one. Pulling in DSPy
would mean a new dependency to re-solve a problem that already has an
in-scope, dependency-free fix queued. **Not proposed as a task this week** —
TASK-977 is the task, and it is already TODO, not written by this survey.

---

## 3. Nango (nangohq/nango) — unified API / connector platform

**What it is.** A platform exposing 400–900+ third-party APIs behind one
unified client, with per-integration schema mapping and a self-hosted option.

**License.** Elastic License 2.0 — **not** an OSI-approved open-source
license. It permits self-hosted internal use and modification but prohibits
reselling it as a hosted service to external customers without a commercial
agreement. Naming this plainly because "open source" is in its own
marketing and the license is more restrictive than that implies.

**What it does better than us, concretely.** `src/providers/bison.py`
(104 KB) and `src/providers/heyreach.py` (152 KB) are independent modules
with no shared interface: confirmed again this run that `tests/fakebison.py`
exists and `tests/fakeheyreach.py` still does not (`ls tests/` for
`*heyreach*` returns `test_heyreach_readback.py`,
`test_heyreachfactory.py`, etc. — no fake transport). `set_sequence` takes
`(campaign_id, title, steps)` on Bison and `(campaign_id, sequence)` on
HeyReach. A platform like Nango normalizes exactly this kind of per-provider
signature drift behind one schema.

**What it would mean here.** This is the same asymmetry
`docs/qwen-tasks/TODO/TASK-273-...md` already documents in detail (still
TODO, sized M, explicitly scoped to build a conformance suite against the
*transport* contract that already exists rather than inventing a sequencer
interface). Nango would also be a new dependency sitting in front of two
provider modules this codebase deliberately keeps isolated behind
`guard_prospect_facing()` and a private write allowlist
(`src/providers/__init__.py`) — adopting a generic connector platform here
would mean re-deriving those safety chokepoints for a third-party library
instead of the two modules that currently carry them. **Not proposed as a
task this week** — TASK-273 already covers the real work.

---

## 4. Guardrails AI (guardrails-ai/guardrails) — LLM input/output validation framework

**What it is.** A Python framework for validating LLM inputs and outputs
against declared schemas and a hub of community validators (PII detection,
topic restriction, structured-output enforcement via Pydantic).

**License.** Apache-2.0.

**What it does better than us, concretely.** It is a general, reusable
validator runtime with a growing library of pre-built checks (PII,
toxicity, topic restriction) that `src/lint.py` would otherwise have to
hand-write one at a time, the way `BANNED_PHRASES` (`:303-387`) already is.

**What it would mean here.** `src/lint.py:648-694` (`check`) and
`contract_code`/`explain_contract` (`:624-647`) enforce a word-count
*equality*, not a range — the standing rule from CLAUDE.md/TASK-943 that two
authorities intersect to exactly one legal length for `em2` — plus a
greeting-name match (`:577-624`) tied to this estate's own contact-record
shape. That is estate-specific business logic, not a generic "is this
output well-formed" check, and Guardrails would sit alongside it rather than
replace it. The part Guardrails is actually good at — generic PII/toxicity
detection — is not a gap this survey could confirm: `src/lint.py` has no PII
check today, but whether that is a real exposure or a non-issue (copy is
generated from vetted pack facts, never from free user input) is a question
about the writer's input surface, not about `lint.py` itself, and checking
that needs a read of `src/generate_campaign.py`'s prompt assembly deeper than
this hour allowed. **Not proposed as a task this week** — flagging the
open question rather than guessing an answer.

---

## What this week's survey is actually worth

Three of four candidates would duplicate work already queued and unstarted
(`TASK-977`, `TASK-273`); the fourth (Talon) would be guessing at the size of
a problem with no live data to measure it; and all four would cost a new
dependency this repository's rules forbid adding without the operator's
decision. The honest output of checking four real candidates against real
code this week is: **nothing to adopt, and two already-queued tasks
reconfirmed as still the right shape** (TASK-977's Defect B, TASK-273's
adapter asymmetry) rather than superseded by something better outside.
