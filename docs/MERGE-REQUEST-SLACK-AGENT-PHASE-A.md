# Merge request — `slack-agent` Phase A

**For the main session. Nothing on this branch touches production; read
section 3 before merging, because it changes three files the main session
also owns.**

Branch `slack-agent`, forked from `master` at `8e2289ba`. Worktree
`../resonate-slack-agent`.

What it is: `docs/SLACK-AGENT-PHASE-A.md`. What follows is only what the
main session needs to decide.

---

## 1. THE DIFF

**Five new modules and five new test files, all self-contained:**

    src/slackscope.py              the isolation boundary
    src/slackknowledge.py          the knowledge pack
    src/slackagenttools.py         fourteen bounded read-only tools
    src/slackconversation.py       one turn: memory, planning, guards
    docs/SLACK-AGENT-PHASE-A.md
    docs/requests/README.md        the Phase B ticket contract, reserved

    tests/test_slack_agent_cannot_act.py      10 tests
    tests/test_slack_agent_scope.py           39
    tests/test_slack_agent_numbers.py         16
    tests/test_slack_agent_conversation.py    24
    tests/test_slack_knowledge.py             20

**Three existing files modified.** These are the merge risk:

    scripts/slack_agent_loop.py        rewritten     -391/+270
    src/workspaces.py                  +33, additive
    tests/test_slack_agent_readback.py repaired      see section 4

**`src/slackagentreadback.py` IS NOT TOUCHED**, deliberately. The main
checkout has uncommitted changes to it — `stages()` and `batch_state()`
that the fork point does not carry — and two sessions editing one file is
how the evening gets spent on a conflict rather than on the product.
`slackagenttools.batch_state` and `held_by_reason` **delegate** to those
functions when the module has them and read the campaign store themselves
when it does not:

    canonical = getattr(readback, "batch_state", None)
    state = canonical() if callable(canonical) else _batch_state_local(scope)

So merging in either order works, and merging the main session's version
makes it the one that runs. **Delete the local fallbacks once that lands** —
they exist only to bridge the fork, and a second copy of a readback is
exactly the "two representations of one truth" CLAUDE.md warns about.

---

## 2. WHAT YOU HAVE TO DO TO RUN IT

One line in `config/.env`:

    SLACK_AGENT_MODEL=anthropic/claude-opus-5

`LLM_MODEL` is `openai/gpt-4.1-mini` — the right model for thousands of
drafts and the wrong one for a conversation a person reads. The operator
asked for the strongest model in the llm config with a 20-second latency
budget; measured latency on Opus 5 is 13–20s for two calls per turn, and
the answers in section 1 of the phase doc are what it produces.

**The code does not choose this for you.** With `SLACK_AGENT_MODEL` unset it
falls back to `LLM_MODEL` and prints a line saying so at startup, because
picking a model is picking a spend and that is the operator's call — the
same separation `llm.from_env` already makes between "a credential exists"
and "this run may spend money".

Optional: `SLACK_INTERNAL_CHANNELS=C0C34GCAR27,C0C3C6MDN9L`. The ops and
status channels are internal automatically, so this is only needed for a
third internal channel.

Then, exactly as before, restart-bare and never under `timeout`:

    py -3 scripts/slack_agent_loop.py

---

## 3. THE CHANGE TO `src/workspaces.py`

Three keys added to `POLICY_KEYS`, nothing removed, nothing renamed:

    slack.agent_channel      where the agent answers AS this client
    slack.workspace_users    Slack user ids that are this client's people
    slack.internal_users     Slack user ids on the Resonate team

`tests/test_workspaces.py`, `test_client_settings.py`, `test_web_settings.py`,
`test_personas_settings.py`, `test_icp_settings.py` and
`test_workspace_isolation_attacks.py` — 158 tests — are green against it.

**`slack.agent_channel` is deliberately not `slack.workspace_channel`.**
The existing key says where a workspace's notifications are posted. This one
says where a conversational agent may answer anything it is asked about that
client. A channel can be a fine place to receive a positive-reply alert
without being a room where somebody may ask the agent anything they like,
and ISSUE-005 in the register is still open on exactly the question of which
Productive channel is which. **Reusing the notification key would have
bound the agent to a client channel as a side effect of a routing decision
nobody had finished making.**

No workspace has `slack.agent_channel` set. Until the operator sets one,
every client channel resolves `unbound` and the agent gives generic answers
there — which is the intended Phase A behaviour, not a gap.

---

## 4. TWO DEFECTS FOUND IN EXISTING CODE, AND WHAT I DID

### 4a. `tests/test_slack_agent_readback.py` had nine tests that had never
passed — REPAIRED on this branch

Measured at the fork point, `8e2289ba`, before any of my changes:
**1 failure and 8 errors of 19 tests.** Identical after. So this branch adds
no failure there; it removes nine.

What was wrong:

- `HostileMessagesAreAnsweredNotActedOn` — six tests — read a system prompt
  from `prompts/slack_agent.md`. That file does not exist and never has, so
  every one of them errored on `FileNotFoundError`. **This was the class
  guarding the single most safety-relevant property the agent has**, and it
  had been guarding nothing. It also called `model.complete`, so it would
  have reached a real endpoint the moment a credential was present — a live
  call inside the offline suite. It now runs against `llm.NoModel` and
  asserts the real property through `slackconversation.respond`.
- `OneAnswerPerMentionAcrossRestart` — two tests — imported `AnsweredTracker`
  from the loop. No such class has ever been in it. The real mechanism is
  the answer log, which is better than a side file: the record that proves
  an answer was given and the record that prevents a second one are then the
  same record and cannot disagree. Rewritten against `answered_already()`.
- `test_campaign_by_id_reports_missing` asserted the string `"not found"`,
  which the module has never produced — and it called the **real provider**
  to find that out. Rewritten to stub `bison.campaign` and assert the
  contract that matters: a failed readback says it failed and never falls
  back to a zero that would read as "nothing was sent".

This is ISSUE-006's lesson on a different file. A red guard catches nothing,
and these had been red long enough that the loop's own docstring cited one
of them by a filename that did not exist.

### 4b. `slackagentreadback.blocked()` counts bullets, not issues —
NOT FIXED, reported here

`blocked()` walks the `## OPEN` section of the problem register and counts
every line starting with `- `. The register has **10 issue rows, 6 of them
open**. `blocked()` reports **47**.

An agent answering "47 open issues" is worse than one answering nothing: it
is a number, and numbers get quoted. I did not fix it, because
`slackagentreadback.py` is the file the main session is editing. Instead
`slackagenttools.open_issues()` parses the `### ISSUE-nnn` headings and is
what `next_actions` reports, so the agent is correct today. **Please fold
the fix into `blocked()` and point the tool at it**, because `blocked()` has
other callers.

---

## 5. WHAT TO VERIFY BEFORE MERGING

    py -3 -m unittest tests.test_slack_agent_cannot_act \
        tests.test_slack_agent_scope tests.test_slack_agent_numbers \
        tests.test_slack_agent_conversation tests.test_slack_knowledge \
        tests.test_slack_agent_readback tests.test_slack \
        tests.test_slack_route tests.test_web_slack

225 tests, green on this branch. Then the workspace suites named in
section 3: 158 tests, green.

Then, without posting anything:

    py -3 scripts/slack_agent_loop.py --rebuild
    py -3 scripts/slack_agent_loop.py --ask "what is running right now, \
        and has anything actually sent?" --as-channel C0C34GCAR27

**Every guard on this branch was mutation-tested** — broken deliberately,
suite re-run, restored. Seven mutations, six caught on the first pass. The
one that was not is written up in section 9 of the phase doc; it found a
vacuous-pass bug of the same shape as F-003, and both the bug and the
missing test are fixed.

---

## 6. WHAT IS NOT IN THIS MERGE

Phase B — channel binding for a live client, client mode, change-request
tickets, the operator approval flow — is not here. The scoping machinery it
needs is, and it is tested with two synthetic workspaces so the assertions
do not depend on how Productive happens to be configured today.

Phase A does not bind a single client channel, does not write a single
ticket, and cannot change anything. A change request gets an honest sentence
saying what will happen instead.
