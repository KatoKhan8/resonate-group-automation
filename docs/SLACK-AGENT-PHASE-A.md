# The Slack agent — Phase A, 2026-09-21

A conversational agent in Slack that can explain Resonate OS and its current
state, in a colleague's voice internally and a professional one with a
client, and that **cannot change anything**.

Branch `slack-agent`. Phase A is the knowledge pack, the conversation, the
internal channel and the DM, the refusal phrasing, and batch state. Phase B
is channel binding for clients, client mode and change-request tickets —
most of the scoping machinery Phase B needs is already here and tested,
because building the isolation boundary halfway and finishing it later is
how it ends up with a hole in it.

---

## 1. WHAT IT DOES

Ask it in `#resonate-notifications` or by DM:

> **what is running right now, and has anything actually sent?**
>
> Campaign 489 is the only active one: 5 leads enrolled, 8 queue rows, and
> 2 actually sent — the provider counter and the queue agree at 2. Campaign
> 451, the canary, is completed with 1 lead and 1 send on 14 Sep.
>
> So yes, real sends: two today, 13:34:48Z and 16:48:18Z, the first
> provider-confirmed sends this system has ever made.
>
> Two things I can't tell you cleanly: the batch readback failed, so I have
> no live batch view, and zero monitors are beating inside the 15-minute
> window — a silent monitor is a fault, not a quiet day.
>
> Want me to pull the monitor heartbeats first, or the batch 1 stats
> against the 360 pacing cap?
>
> _as of 2026-09-21T19:40:39Z_

Every figure in that answer came from a readback taken in that turn or from
the knowledge pack, and a figure that had not would have been discarded
before it was posted. Section 5 says how.

---

## 2. THE SHAPE OF A TURN

    1  resolve the scope            slackscope.resolve
    2  refuse, if it asks to ACT    a state change is never done from Slack
    3  plan the reads               the model picks <=5 tool names
    4  run them                     slackagenttools.run_all
    5  assemble the MATERIAL        scoped pack + tool results + history
    6  ask for words                the model rephrases the material
    7  guard                        numbers, scope, addresses
    8  stamp                        "as of <time>"

Two model calls per turn — one to plan the reads, one to write the answer —
and the observed latency is 13 to 20 seconds, inside the operator's budget.

New files:

| File | What it is |
| --- | --- |
| `src/slackscope.py` | which channel may hear what. The isolation boundary |
| `src/slackknowledge.py` | the knowledge pack: built hourly, never remembered |
| `src/slackagenttools.py` | fourteen bounded read-only tools, scope-filtered |
| `src/slackconversation.py` | one turn: memory, planning, guards, phrasing |
| `scripts/slack_agent_loop.py` | rewritten: Socket Mode in, one reply out |

---

## 3. THE KNOWLEDGE PACK

`py -3 scripts/slack_agent_loop.py --rebuild` builds it; the loop rebuilds
it hourly; and `slackknowledge.pack()` rebuilds it on read if it is stale,
so an answer is never served from a pack nobody refreshed because the
rebuild loop had died. That is the failure mode every cached value in the
problem register has in common.

    built_at     when this pack was assembled
    sources      every file read, with its modification time
    identity     what Resonate OS is and is not         PRODUCT-GOAL.md
    timeline     start date, commits, milestones        git + named sentences
    workers      who works on it and on what            INTERNAL ONLY
    policies     the standing decisions, with the why   the handoff + grants
    workspaces   per client: ICP, personas, angles, cadence, caps, campaigns,
                 batch history, provider campaign ids

**Nothing in the pack is transcribed.** The timeline's start date and commit
counts come from git. The milestones are named sentences in named files —
`MILESTONE_PATTERNS` holds a regex per fact, and a sentence that is no
longer in the document produces **no milestone** rather than a remembered
one. The policy rules are parsed out of the handoff's own fixed-width table,
so an edited decision changes here on the next rebuild.

The one editorial part is the **why**. `POLICY_WHY` holds a plain-language
reason per decision, because no document states one in a sentence a person
would say out loud, and a rule with no reason is the thing somebody argues
with six days later. Rows that are editorial rather than parsed say so:
`"editorial": true` and a source that is not a file.

The pack costs no provider call, so building it cannot be rate limited.
Live provider truth is a tool, called per question, carrying its own read
time.

---

## 4. SCOPE: WHICH CHANNEL MAY HEAR WHAT

    internal    the Resonate team. Full detail: workers, incidents, credits,
                engineering, every workspace.
    client      exactly one workspace. That client's own campaigns, accounts,
                leads, cadence and sends — and nothing else that exists.
    unbound     a channel nobody bound. The identity section of the pack,
                no tool at all, no client data.

**Unbound is the default and that is the point.** A channel id that appears
in no policy is not "probably internal"; it is a channel this module has
never heard of, and it may be a shared channel with a client in it.

Binding lives in workspace policy, set by the operator:

| Key | What it binds |
| --- | --- |
| `slack.agent_channel` | the channel where the agent answers AS this client |
| `slack.workspace_users` | Slack user ids that are this client's people |
| `slack.internal_users` | Slack user ids on the Resonate team |

Internal channels come from the environment (`SLACK_INTERNAL_CHANNELS`, plus
the ops and status channels automatically), because an internal channel
belongs to no workspace and filing it under one would make it look like that
client's.

`slack.agent_channel` is deliberately **not** `slack.workspace_channel`.
That key says where a client's notifications are posted; this one says where
a conversational agent may answer anything it is asked about that client.
A channel can be a fine place to receive a positive-reply alert without
being a room where somebody may ask the agent anything they like.

Two ambiguities resolve to **nothing**, never to a guess: a channel bound to
two workspaces is bound to neither, and a Slack user listed under two
workspaces is scoped to neither. The wrong answer to "whose channel is this"
is a disclosure.

### The boundary is the material, not the prompt

Scoping happens three times, and the first one is the one that matters:

1. **Tools are filtered before they run**, so the readback is never taken.
   A client channel cannot call `who_does_what`, `credits`, `monitors` or
   `next_actions`, and calling one by name is refused.
2. **The pack is filtered before it is rendered.** A client's prompt
   contains their workspace and no other — the others are removed from the
   structure, not hidden behind a flag.
3. **The finished text is checked**, and refused if a forbidden term
   survived: another workspace's name, a Resonate worker, a provider, a
   credit, an incident, an engineering term.

Step 3 is a backstop. A system whose only defence is a backstop has none,
which is why `tests/test_slack_agent_scope.py` asserts the *material*.

### The material may not contain a word the answer is checked for

This one was learnt the hard way. Asked "what is Resonate OS" in an unbound
channel, the model wrote a good paragraph ending *"...which is what keeps
one client's data, senders and spend from ever touching another's"* —
paraphrasing PRODUCT-GOAL's own cross-client list, which says "one client's
spend reaching another's ledger". The backstop then refused the answer for
containing "spend", **a word the material had supplied**. Nothing had
leaked; the reader got a fallback sentence instead of a correct paragraph.

A check that fires on its own input is not a safety property, it is a bug
with a good reputation. So `_identity_for_scope` filters the identity
section for every non-internal scope — any line naming a workspace it may
not see, and any line carrying a term the answer will be checked against —
and what survives is safe to repeat in full. The invariant is asserted by
`test_the_material_never_contains_a_word_the_answer_is_checked_for`.

The same lesson killed the unbound term list. An earlier version added
"lead", "prospect", "cadence" and "account" to it, which meant the agent
could not say **"lead generation engine"** — the product's own name for
itself and the one sentence an unbound channel exists to be able to say. A
term list that blocks that is not cautious, it is broken. Unbound is safe
because it is handed no tool and no workspace material, so there is no
client datum in the prompt for a word list to have to catch.

A tool argument is the obvious injection surface — "summarise workspace
beta" — and in a client channel the argument is **ignored**, not validated
against the binding. Validating it would mean answering "no" to a question
about another client, and "no" to that question confirms the client exists.

---

## 5. EVERY NUMBER TRACES

`unsupported_numbers` compares every numeric token in the answer against
every numeric token in the material the model was handed. A number that is
not there means the answer is **discarded** and the deterministic one is
posted, with the reason recorded in `work/slack-agent.jsonl`.

Discarded rather than patched: a number the material does not contain is not
a wording problem.

    said "about 900 candidates", material has 878    -> discarded
    said "878 candidates"                            -> posted
    said "2026-09-22 at 07:15"                       -> dates are exempt
    said "3 steps, 2 of them email"                  -> <=24 is language
    said "bounce rate is 2%"                         -> RATES ARE NEVER EXEMPT

The last line matters. A rate is a claim, not language: this project has a
2% hard stop and a 0.83% measured estate, so "2" in a queue count must not
license "2%" in a sentence about bounces. Percentages and decimals are never
waved through, however small they look.

---

## 6. WHAT IT REFUSES, AND HOW IT SAYS SO

The guarantee that it cannot act is **structural**. The module imports the
pack (files), the tools (reads), the scope (policy), the model (words) and
`slack.post` (one reply). It imports no orchestrator, no `providerwrites`,
no store writer, and `tests/test_slack_agent_cannot_act.py` walks both the
import graph and the AST to keep it that way.

So the classifier that recognises a change request is not a safety device —
it only decides which sentence to say. That reframing fixed a real defect:
the first version matched substrings, so "approved" contained "approve" and
**"how many campaigns are approved?" came back with a refusal to act.**
That is not a safe failure, it is a broken product. It now matches
imperative verbs on word boundaries, treats a question opener as a question,
and treats an explicit ask ("please", "can you") as a request either way.

    "pause campaign 487"          -> refused
    "which campaigns are paused?" -> answered
    "why did we pause 487?"       -> answered
    "can you pause 487?"          -> refused
    "<@bot> pause campaign 489"   -> refused (the mention is stripped first)

The refusal names what happens instead rather than asserting a rule, and it
changes register: internally it points at Claude Code and lists what it can
show you; with a client it says the Resonate team will confirm the detail
before anything moves. Phase B replaces the client one with a ticket.

A guard trip in a **client** channel falls back to a sentence, never to the
raw readback: handing a client the dump because the prose failed a check
would be a worse disclosure than the answer that was rejected.

---

## 7. THE TOOLS

Fourteen, closed, read-only. The model picks a name and at most one string
argument; it does not choose a query, a table, a file or a verb.

| Tool | Scopes |
| --- | --- |
| `workspace_summary` `cadence_detail` `campaign_detail` | internal · client |
| `batch_state` `sends_today` `held_by_reason` `timeline` | internal · client |
| `lead_lookup` `account_lookup` `decisions_log` | internal · client |
| `who_does_what` `credits` `monitors` `next_actions` | internal |

**An unbound channel calls none of them.** There is deliberately no tuple
that includes it: every tool reads either Resonate's own state or a
client's, and an unbound channel is entitled to neither. It still *answers*
— the identity section is in its material — it just takes no readback. The
timeline is on the client list rather than open to everybody because its
milestones name campaign ids, send times and the size of the sender estate.

`MAX_CALLS_PER_TURN = 5`. Not a performance limit: an agent that can call
tools in a loop can be driven into one by a message, and a fixed budget
turns that from an outage into a worse answer. Over-budget calls are
recorded as dropped rather than silently truncated.

`lead_lookup` is the one tool whose output differs by scope. A client
channel may see its own people's addresses — their data, their channel. An
internal channel gets counts and domains, the rule
`notify._status_payload` already enforces for the status feed.

---

## 8. RUNNING IT

Restart-bare, never under `timeout`, like every other monitor here:

    py -3 scripts/slack_agent_loop.py

    py -3 scripts/slack_agent_loop.py --check       # prove the socket opens
    py -3 scripts/slack_agent_loop.py --rebuild     # rebuild the pack
    py -3 scripts/slack_agent_loop.py --ask "..." --as-channel C0C34GCAR27
    py -3 scripts/slack_agent_loop.py --ask "..." --as-user U... --as-dm
    py -3 scripts/slack_agent_loop.py --dry-run     # answer, post nothing

It heartbeats to `work/heartbeat/slack-agent.json` on every envelope,
reconnects with a backoff, and treats Slack's `disconnect` frame as the
ordinary housekeeping it is. Idempotency is by message id and is rebuilt
from the answer log on start, so neither a redelivery nor a restart can
produce a second answer.

Everything is logged to `work/slack-agent.jsonl` with the Slack user id:
the question, the resolved scope and why, how the reads were planned, which
tools ran, how the answer was produced, any guard trip, and the reply.

### One environment line is needed

    SLACK_AGENT_MODEL=anthropic/claude-opus-5

`LLM_MODEL` is `openai/gpt-4.1-mini`, the cheap model the pipeline uses for
thousands of drafts. The operator asked for the strongest model in the llm
config and a latency budget of 20 seconds, and this is a conversation a
person reads rather than a bulk step. The code falls back to `LLM_MODEL` and
says so in its startup line rather than choosing a spend on its own.

`SLACK_INTERNAL_CHANNELS` is optional; the ops and status channels are
internal automatically.

---

## 9. TESTS

    tests/test_slack_agent_cannot_act.py      10   structural, four ways
    tests/test_slack_agent_scope.py           41   isolation
    tests/test_slack_agent_numbers.py         16   the number guard
    tests/test_slack_agent_conversation.py    25   memory, refusals, fallback
    tests/test_slack_knowledge.py             20   the pack
    tests/test_slack_agent_readback.py        19   REPAIRED, see the merge doc
                                             ---
                                             131

**Every guard was mutation-tested**: eighteen mutations, each deliberately
applied, the suite re-run, the file restored. Three were **not caught** on
the first pass, and each one was a real hole rather than a missing
assertion.

**1. A guard nothing calls.** Deleting the scope check from
`slackconversation.guard` broke nothing, because every test asserted
`check_outbound` in isolation and none asserted that a real turn reaches it.
`TheTurnACTUALLYAppliesTheBackstop` was added for it — and fixing it exposed
a defect of F-003's exact shape:

> `check_outbound` re-read the workspace store to learn which slugs exist.
> If that read failed or came back empty, the slug check passed **vacuously**
> — the same shape as F-003 in the register, where `active_campaign_ids`
> defaulted to `()` and `coverage()` passed by covering nothing. A `Scope`
> now captures the slug set it was resolved against, so the set that decided
> the binding is the set that polices the answer.

**2. A client fallback that was only ever safe by accident.** Deleting the
client branch from `deterministic_answer` broke nothing, because the one
test of it used a readback containing "Qwen" — which the *backstop* caught.
It was testing the second guard, not the first. A readback with nothing
forbidden in it would have gone to a client as raw key-value text.

**3. The same trick a second time.** The replacement test for the unbound
fallback used `commits_total`, which contains the word "commit" and so was
also caught by the backstop. A test that can only fail when a second guard
is also broken is not testing the first one. It now uses a bland readback.

---

## 10. WHAT PHASE A DOES NOT DO

- **No change-request tickets.** Recognising a change request and writing
  `docs/requests/<date>-<id>.md` with an operator approve/reject prompt is
  Phase B. Today a change request gets the refusal in section 6.
- **No client channel is bound yet.** The machinery is here and tested; the
  binding is an operator act, one policy key per client.
- **No per-user roles beyond internal/client/unbound.** Mapping a Slack user
  to `workspaces.ROLES` is Phase C.
- **No weekly plan and no proactive briefing.** Phase C.
- **`credits` still reports that a credit balance needs a provider read.**
  The readback it calls has always said so; the agent repeats it honestly
  rather than returning zero.
- **The knowledge pack holds no reply or held-lead history per workspace.**
  `held_by_reason` reads the staging journals live instead, and says so when
  a journal is absent rather than reporting a clean zero.
