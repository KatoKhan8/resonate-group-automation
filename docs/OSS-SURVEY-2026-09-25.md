# Weekly OSS survey — 2026-09-25

Standing survey, set up by the operator on 2026-09-23. Eight candidates
across seven areas of `CLAUDE.md`'s architecture, read **as data**, checked
against the actual code rather than assumed. One hour time box.

Every claim below is grounded in a file:line citation from this repository
or in a verified GitHub repo fact (license file, star count, last commit).
Anything that would need `work/` — gitignored, not present in this clone —
is marked `UNVERIFIED (needs work/):` naming exactly what file and count
would answer it.

---

## 0. READ THIS FIRST: the premises that did not survive being checked

| # | The premise | What is actually true |
|---|---|---|
| 1 | Warmbly's client-side warmup ramp (10/day, +1/day to a 40/day ceiling) would close a rate-limiting gap | `src/senderinventory.py:23` already states the house rule as a comment: *"Guess a limit. `daily_limit` comes from the provider or stays `None`."* Adopting a self-computed ramp means guessing exactly the number that line refuses to guess. The gap is real (no code paces the ramp itself) but the fix Warmbly represents is the one this codebase has already decided not to build. |
| 2 | PyBandits' Thompson sampling would improve how traffic shifts to a winning copy variant | `src/variants.shifted_allocation()` — the far simpler algorithm already in the codebase — has **zero production callers**. `grep -rn "shifted_allocation" src/ scripts/` returns exactly one call site: `src/web/demovariants.py:218`, a demo web surface. Nothing that writes a real campaign's `node["variants"][i]["allocation"]` calls it. Upgrading the statistics of a function nothing production reads is the same defect CLAUDE.md already names three times for `learning.boost()`, `slackfollowup.due()`, and the unassembled report sections. |
| 3 | ai-sdk-slackbot's OPA/Rego policy gate is a stronger permission boundary than what we have | `src/slackscope.py:10-22` already enforces the client/internal/unbound boundary **three times** — tool filtering, knowledge-pack filtering, and an outbound-text backstop — and its own docstring states the design principle OPA is one instance of: *"a system whose only defence is a backstop has none."* A fourth, external policy layer would add a dependency (forbidden) for a boundary already defended in depth. |
| 4 | email-one-click-unsubscribe means a new task | `TASK-271` (open, unstarted, `docs/qwen-tasks/TODO/`) already scopes this exact gap — `List-Unsubscribe` is absent from the whole repository (confirmed again this run: zero hits) and TASK-271 already requires the honest choice between an `email_body` link and a provider-level header setting. The OSS repo is corroborating evidence for TASK-271's approach, not a reason to write a second task. |
| 5 | LiteLLM's provider-conformance-suite pattern means a new task | `TASK-273` (open, unstarted) already scopes this exact gap — no shared `Protocol`/ABC across `src/providers/bison.py` and `src/providers/heyreach.py`, confirmed again this run by grep. LiteLLM (100+ adapters, one shared `tests/` suite) is the clearest real-world proof that TASK-273's own design — naming each asymmetry as an expected-difference row rather than a red test — is the right shape, not a reason to duplicate it. |
| 6 | open-intent-classifier / outreachgraph would improve reply classification | `src/replies.py` already runs 9 policy categories plus 6 analysis-only sub-labels, rule-based (`classify_rules`, `classify_taxonomy`), confirmed by grep that every production caller passes `model=None` — no LLM classification runs today, by design, with the LLM seam kept but unused. `outreachgraph` does the identical "deterministic rules first, model for the remainder" shape we already ship, but it is a same-week, 0-star, no-LICENSE, single-maintainer repo (commits co-authored "claude"). Nothing to adopt from either. |
| 7 | ICP/lead-scoring OSS tools exist to compare `src/icp.py` against | None found. Every repo surfaced (`ai-lead-qualification-configurable`, `ai-lead-scoring-engine`, `icp-scoring-routing-engine`, etc.) is an unverified, unstarred, single-maintainer demo. The real market for this category is commercial (Clay and similar), not open source. Reported honestly as no match rather than stretched. |

Two items did **not** collapse: the underlying gaps candidates 1 and 2
pointed at are real, just not the fix the candidate offers — see their
sections below for what a grounded task looks like instead.

---

## 1. Warmbly — cold-email warmup / sender-rotation platform

**What it is.** Self-hosted cold-email + warmup app: OAuth mailbox
connection, a worker queue, and a per-mailbox warmup ramp that starts new
mailboxes at 10 sends/day and increases by 1/day to a 40/day ceiling.

**LICENSE.** Apache-2.0 (verified in the repo's `LICENSE` file).

**What it does better, concretely.** It has a *ramp*, and this repo does
not: `src/senderheadroom.py` answers **when** a mailbox has a free slot
against a provider-reported `daily_limit` (`THE-SEND-DATE-IS-THE-MAILBOX`
doctrine), but nothing here paces how that limit should grow while a
mailbox is warming. That is a genuine capability Warmbly has and we don't.

**What adopting it would actually mean here — and why the answer is no.**
`src/senderinventory.py:23` states the house rule in so many words: the
daily limit is read from the provider or left `None`, never guessed. A
client-side ramp is a client-side guess about a number EmailBison and
HeyReach are the sole authority on. Building Warmbly's ramp here would
mean reversing a decision this codebase already made and documented for a
reason (`daily_limit` guesses have burned this project before — see
`docs/THE-LIMIT-BOOKS-SOFT-AND-SENDS-HARD-2026-09-20.md`, cited from
`senderheadroom.py:39-46`). **No task written.** If a ramp is ever wanted,
it belongs behind a provider-truth read of the provider's own warmup
schedule, which is a different, larger, provider-adapter task — not a
survey-sized one.

**A second data point, not a candidate.** `BlackSyncColdEMail`
(MIT-licensed but 0 stars, no real adoption signal) claims the same
feature set plus AI reply classification. Included only to show the
category has one more unproven entrant; not worth reading further.

---

## 2. PyBandits (Playtika) — multi-armed bandit library

**What it is.** Stochastic and contextual multi-armed bandits via Thompson
Sampling with Beta/Bernoulli conjugate priors — company-backed (Playtika),
small and readable source, installable as a pip package.

**LICENSE.** MIT (a vendored `certifi` copy carries MPL-2.0, unrelated to
the library code itself).

**What it does better, concretely — checked against `src/variants.py`.**
`shifted_allocation()` (`src/variants.py:526-545`) already does traffic
reallocation toward a winner, deliberately never to 100% (*"a variant that
stops being served stops being measured"*, its own docstring), using a
fixed `winner_share = 0.75`. PyBandits' posterior sampling would replace
that fixed split with an allocation that widens or narrows automatically
with the strength of the evidence — a real statistical improvement over a
constant.

**But the premise check changes what's worth building.** `grep -rn
"shifted_allocation" src/ scripts/` returns exactly one caller:
`src/web/demovariants.py:218`. Nothing that writes to a real campaign's
`node["variants"][i]["allocation"]` calls this function. **The simple
version isn't wired to production at all** — the same "computed correctly,
consumed by nothing" shape as `learning.boost()` (still zero non-test
callers, reconfirmed this run) and the report sections and
`slackfollowup.due()` CLAUDE.md already names. Swapping the math on a dead
function is worse than useless: it adds surface nobody exercises.

**So the task below is not "adopt Thompson sampling."** It's "find or
build the one thing that reads a `WINNER` verdict and changes what a real
contact is actually assigned next time — and only then does upgrading the
formula make sense." → **TASK-279**, size S.

---

## 3. ai-sdk-slackbot (Vercel Labs)

**What it is.** A Slack bot on the Vercel AI SDK whose tool calls are
gated by Open Policy Agent (Rego) policies kept as separate declarative
files from the tool code.

**LICENSE.** MIT. 132 stars, last commit 2026-06-05.

**What it does better, concretely.** Nothing, once checked.
`src/slackscope.py` already enforces the client/internal/unbound boundary
three separate times (`Scope.tools()` removes disallowed tools before any
call happens, `Scope.filter_pack()` strips other workspaces from the
knowledge pack, `Scope.check_outbound()` is a backstop on the rendered
text) — a stronger, more layered design than a single external policy
gate on tool invocation. Declaring policy as data outside the code is a
reasonable idea in general, but `SCOPES`/scope resolution here is already
close to that shape (`resolve()` fails closed to `unbound`, `slackscope.py`
top). Adopting OPA itself is forbidden (new dependency) for a boundary
that is not, on inspection, weaker than what OPA would provide.

**No task written.**

---

## 4. email-one-click-unsubscribe (aws-samples)

**What it is.** AWS reference implementation (CDK) of RFC 8058
`List-Unsubscribe` / `List-Unsubscribe-Post` one-click headers, optionally
feeding Amazon SES's suppression list.

**LICENSE.** MIT-0. 8 stars, last commit 2025-04-10 — an AWS reference
sample, not an actively maintained product; treat as reference code only.

**What it does better, concretely.** It's a real, working example of the
exact thing `TASK-271` already identifies as missing here: repo-wide grep
for `List-Unsubscribe` returns zero hits (reconfirmed this run), and
`src/providers/bison.py:1467-1513`'s sequence-step payload has no header
field — only `email_body`. This sample shows the shape a fix needs to
take: either a link inside `email_body`, or a provider-level setting
outside the sequence-step payload entirely.

**What adopting it would mean here.** Nothing new to write — `TASK-271`
already exists, is unstarted, and already requires the same honest choice
this sample makes concrete. **No new task; this strengthens TASK-271's
existing acceptance criteria.**

---

## 5. LiteLLM (BerriAI)

**What it is.** A unified "OpenAI-format" interface that 100+ LLM
provider adapters implement, verified by one large shared conformance
test suite.

**LICENSE.** MIT for the core tree; the `enterprise/` subfolder carries a
separate commercial license per LiteLLM's own `LICENSE` file — note this
qualifier if citing it as simply "open source." 59.6k stars, committed
today.

**What it does better, concretely.** It's the cleanest real-world
instance of the exact pattern `TASK-273` already proposes for
`src/providers/bison.py` and `src/providers/heyreach.py`: no shared base
class exists between the two today (reconfirmed this run — no `Protocol`,
no ABC, no `abstractmethod` anywhere in `src/providers/`), and where verb
names coincide the signatures differ (`set_sequence(campaign_id, title,
steps)` on Bison vs. `set_sequence(campaign_id, sequence)` on HeyReach).
LiteLLM proves at scale that the *conformance-suite-with-named-exceptions*
shape — not a naive "green suite" — is how real projects manage this
divergence, which is exactly what TASK-273 already specifies (an
"expected-difference row" rather than a red test on day one).

**What adopting it would mean here.** Nothing new to write —
**strengthens `TASK-273`'s existing design**, does not replace it. No new
task.

---

## 6. Reply classification: open-intent-classifier and outreachgraph

**open-intent-classifier** (SerjSmor) — T5 + embedding + LLM intent
classification with dynamic labels, 59 stars. **No LICENSE file found in
the repo — not permissively licensed, say so plainly.** Generic-purpose,
not email-specific.

**outreachgraph** (profullstack) — classifies replies into
interested/not_interested/question/out_of_office/unsubscribe_request/
referral/bounce/other; deterministic rules first (headers, DSNs,
stop-phrases), model for the remainder. **0 stars, no LICENSE file
present (raw fetch 404s), single-maintainer, commits co-authored "claude,"
last commit 2026-09-24** — a days-old, unproven, unlicensed project.

One line in its README describes the product's own anti-persuasion
design ("an agent driving it cannot be talked into breaking a platform's
terms") — flagged per the survey's instructions as prompt-injection-shaped
text found in a surveyed repo. On inspection it reads as marketing copy
about the product, not an instruction aimed at a reading model, and
nothing in it was acted on.

**Checked against `src/replies.py`.** Both projects do a narrower version
of what's already shipped: `src/replies.py` runs 9 policy categories
(`POSITIVE`, `NEUTRAL`, `NEGATIVE`, `UNSUBSCRIBE`, `ACCOUNT_DNC`,
`OUT_OF_OFFICE`, `NOT_NOW`, `REFERRAL`, `NOT_RELEVANT`) plus 6
analysis-only sub-labels, rule-based first (`classify_rules`,
`classify_taxonomy`), with an LLM seam (`model=None` in every production
caller, confirmed by grep across `scripts/task066*.py`, `task058*.py`,
`task108*.py`, `task109*.py`) kept but deliberately unused. This is
already the "deterministic-first, model-fallback" shape both OSS projects
implement, with a wider taxonomy than either. **No task written.**

---

## 7. Lead scoring / ICP — no match found

Searched for open-source ICP/lead-qualification scoring tools comparable
to `src/icp.py`'s rule-based weighted scoring (`score()`, configurable
`DEFAULT_WEIGHTS`, `MIN_SCORED_DIMENSIONS` confidence floor). Every repo
surfaced was an unverified, unstarred, single-maintainer demo project with
no real usage signal. Reported honestly: **this category doesn't have a
credible open-source project to compare against**; the real market is
commercial platforms (e.g. Clay), not OSS. No task, no false candidate.

---

## Qwen tasks filed this run

**One.** `docs/qwen-tasks/TODO/TASK-279-shifted-allocation-writes-to-nothing.md`,
size S — not "adopt Thompson sampling," but "prove `shifted_allocation`'s
output reaches a real assignment, or say plainly that it doesn't and stop
there." The PyBandits candidate is what prompted the check; the task
itself is about wiring, not about the OSS project's algorithm.

Every other candidate either failed its premise on contact with the code,
duplicated an already-open task (`TASK-271`, `TASK-273`), or had no real
candidate to report (ICP scoring). Per the survey's own instructions, no
task was padded in to make the count look bigger.

## What this run could not verify

`work/` is gitignored and not present in this cloned session. In
particular:

- `UNVERIFIED (needs work/):` how many real client-facing experiments
  currently have a `WINNER` verdict and are silently not reallocating
  traffic because of the TASK-279 finding — would need
  `work/campaigns.jsonl` filtered for `experiment`/`variants` nodes with
  `state == WINNER`, cross-referenced against `work/queue.jsonl` assignment
  history.
- `UNVERIFIED (needs work/):` current `daily_limit` values and warmup
  status per mailbox, to know how many senders are actually warming right
  now and would be affected if a ramp were ever built — would need
  `work/heartbeat/*` or a fresh `senderinventory.refresh()` read.

No number above is guessed; both are named rather than invented.

---

**The operator decides what enters the queue.** Nothing in this survey or
in TASK-279 is approved by writing it down — filing to `TODO/` is a
proposal, not a commit to execute.
