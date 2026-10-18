# Weekly OSS survey — 2026-10-09

Standing survey, set up by the operator on 2026-09-23. One hour time box.
Three candidates, each checked against this repository's actual code rather
than against the candidate's own README or a premise assumed from last
week's survey. The 09-25 and 10-02 surveys already covered Warmbly,
PyBandits, ai-sdk-slackbot, email-one-click-unsubscribe, LiteLLM,
open-intent-classifier, outreachgraph, Temporal, django-anymail and Postal —
none of those is repeated here.

`work/` is gitignored and not present in this clone. Every claim below is
either a file:line citation from this repo, a verified GitHub/license fact,
or marked `UNVERIFIED (needs work/):` naming exactly what would answer it.

---

## 0. Premises checked, and what survived

| # | The premise | What is actually true |
|---|---|---|
| 1 | Listmonk's List-Unsubscribe / bounce handling would close the compliance gap named in `CLAUDE.md` (487/489/493 paused for "no opt-out route") | The gap is real and confirmed (`List-Unsubscribe` has zero hits in the repo; `executionguard.py:590-615` already refuses a cadence step unless the body carries a link or a named provider setting) — but it is **already queued in more precise detail** than Listmonk's own architecture would add: `docs/qwen-tasks/TODO/TASK-271-...md`. Adopting Listmonk here would duplicate a task that already names the exact provider-field absence (`bison.py:1467-1513` has no mail-header field) and the exact refusal pattern to imitate. **No new task — it exists.** |
| 2 | NeMo Guardrails would strengthen `src/slackscope.py`'s scope enforcement for the client-facing Slack agent | It would narrow it, not strengthen it. NeMo's rails operate at the output/semantic layer only — the same position as `Scope.check_outbound()`, step 3 of 3. It has no analogue to `Scope.tools()` (removes callable tools before the model ever runs) or `filter_pack()` (removes other workspaces' data before the prompt is built) — steps 1 and 2, which `slackscope.py`'s own docstring calls "the one that matters." Swapping in a framework whose only enforcement point is the backstop contradicts the file's explicit design principle: *"a system whose only defence is a backstop has none."* **No task.** |
| 3 | tenacity (generic retry/backoff) would clean up the hand-rolled `time.sleep` retry loops in `src/providers/bison.py` and `src/providers/heyreach.py` | Most of those loops are not failure retries at all — they are readback polling, waiting for provider-side state to converge (`bison.py:1546`, `ATTACH_READBACK_INTERVAL`). The code paths that are retry-adjacent are **deliberately not retried**, and say so: `heyreach.py:2791`, *"a less careful caller turns into a blind retry of a verb that starts"* a new, non-idempotent action (a second connection invitation). A generic retry decorator has no notion of which verbs are idempotent; applying it uniformly would reintroduce the exact duplicate-action bug these comments were written against. The one place a thin wrapper would fit (`interval` backoff in polling loops) isn't worth a new dependency over `time.sleep` per CLAUDE.md's "no speculative features." **No task, and the premise actively warns against the dependency rather than merely failing to need it.** |

None of the three premises survived as something worth building. Per the
standing instruction, an empty qwen-tasks queue this week is the honest
output of that finding, not a shortfall — **no task file is written this
week.**

---

## 1. Listmonk — self-hosted bulk/newsletter manager

**What it is**: a Go/Vue newsletter and campaign manager with built-in
one-click `List-Unsubscribe` (RFC 8058), bounce/complaint webhook ingestion,
and subscriber-list suppression.

**LICENSE**: AGPL-3.0-only (confirmed from `LICENSE` at
`github.com/knadh/listmonk`). Copyleft — network use would trigger source-
disclosure obligations under AGPL if any of its code or a derivative were
run as part of a service we operate. Not relevant to the verdict below
since nothing is being adopted, but worth recording: **this is not a
permissively-licensed option** if anyone later proposes vendoring it.

**What it does better, concretely, naming our file**: it has a working
unsubscribe **landing endpoint** — a public route that receives the click
from the mail header/body link, authenticates the token, and writes the
suppression record. Grepping this repo for that exact piece:

    grep -rn "unsubscribe" src/web/*.py   -> only pages.py (display labels),
                                              api.py:5501 (reads an already-
                                              set `contact["unsubscribed"]`
                                              flag from an UPLOADED file)
    grep -rn "/unsubscribe" src/          -> zero hits

So even once `TASK-271`'s gate and document land, there is still no code
path by which a real click on a real unsubscribe link reaches
`agencydnc.add(kind, value, reason=REQUESTED, ...)` — the exact function
that already exists (`src/agencydnc.py:134`) to record it. TASK-271 is
explicit that it scopes out "implement[ing]... the consent store"; it does
not claim to build the receiving endpoint either, and no other task in
`docs/qwen-tasks/` names it.

**Checked against our repo, not assumed**: confirmed by grep above, plus
`executionguard.py:1163` (`_has_unsubscribe_affordance`) and `:1175`
(`_named_unsubscribe_setting`), which only check that outbound copy
*claims* an unsubscribe path exists — neither verifies anything receives a
click. The gate can be satisfied by a body containing a mailto: link that
no running code reads.

**What adopting the idea (never the code) would mean here**: a small,
dependency-free web route — using whatever this repo's existing HTTP
surface is (not Flask/Listmonk's stack; `src/web/api.py` is a pure service
layer with routing elsewhere in the tree, so the task below asks the
engineer to find the real entrypoint rather than assuming one) — that
takes a signed token identifying a contact, calls `agencydnc.add()`, and
redirects to a static confirmation page. This is queued below as
TASK-978, separate from and narrower than TASK-271, because it is the one
piece neither that task nor Listmonk itself (as a dependency) would give
us without copying code or adding AGPL-licensed infrastructure.

---

## 2. NeMo Guardrails — topical/safety rails for conversational agents

**What it is**: NVIDIA's framework for constraining what an LLM-backed
conversational agent may discuss or output, defined in a DSL ("Colang").

**LICENSE**: Apache-2.0 (confirmed from `LICENSE.md` at
`github.com/NVIDIA/NeMo-Guardrails`). Permissive — license is not the
blocker here.

**Why the premise does not survive**: see §0 row 2. `src/slackscope.py`'s
own three-step design (tool removal → pack filtering → outbound check) is
already a superset of what NeMo Guardrails provides, which maps to step 3
only. `tests/test_slack_agent_scope.py` (per the file's own docstring)
asserts on the *material available to the model*, not on the wording of
its output — exactly the distinction NeMo's rails cannot make, since they
operate after generation on text. Introducing it would add a second,
weaker enforcement layer and a new dependency for no capability this
system is missing.

**What it would need to do better than us to be worth adopting**: remove
data or tool access *before* the model runs, the way `Scope.tools()` and
`filter_pack()` already do. It does not. **No task.**

---

## 3. tenacity — retry/backoff decorator library

**What it is**: a widely-used Python retry library (declarative backoff,
jitter, stop conditions) via a decorator or context manager.

**LICENSE**: Apache-2.0 (confirmed from `LICENSE` at
`github.com/jd/tenacity`). Permissive.

**Why the premise does not survive**: see §0 row 3. The specific lines
checked:

    bison.py:1050      time.sleep(interval if attempt else 0.5)   — readback
                       polling after an attach, not a failure retry
    bison.py:1546      time.sleep(ATTACH_READBACK_INTERVAL)        — same
    heyreach.py:1775   time.sleep(interval)                        — same
                       shape, readback polling
    heyreach.py:2791   comment: a careless retry of this verb sends a
                       second, real connection invitation — explicitly
                       NOT retried

A library built to retry "the same call, again, on failure" is a bad fit
for code whose central property, repeated at three separate call sites, is
*"do NOT retry blindly."* Applying `@retry` uniformly is actively
dangerous here, not merely redundant. **No task — and this is recorded as
a candidate the next survey should not re-propose without re-reading these
three comments.**

---

## What's queued

**TASK-978** (`docs/qwen-tasks/TODO/TASK-978-the-unsubscribe-link-has-nowhere-to-land.md`),
`SIZE: S`. Not derived from any surveyed project's code — only from the
idea that a one-click unsubscribe needs a receiving endpoint, which is
true independent of Listmonk and which Listmonk merely illustrates. Scoped
narrower than TASK-271 and does not touch it.

This is the operator's call, not a decision made here: the task sits in
`TODO/` for the operator to accept, reject or re-scope, same as every
other item already in that directory.
