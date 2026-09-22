# Slack agent — handoff, 2026-09-22

Written for a session with no conversation context. Phases A and B are
merged to master and running. One client channel is bound and live. Phase C
has not started.

Read `docs/SLACK-AGENT-PHASE-A.md` and `docs/SLACK-AGENT-PHASE-B.md` for how
it works. This says what is true right now and what is waiting.

---

## 1. WHAT IS RUNNING

    py -3 scripts/slack_agent_loop.py        # restart bare, never under timeout

From the **production checkout**, not a worktree: the agent reads heartbeats,
the queue and the roster from wherever it is started, and a worktree has
none of them.

Configured in `config/.env`:

    SLACK_AGENT_MODEL=anthropic/claude-opus-5
    SLACK_OPERATOR_USER=U07KWV94J0H
    SLACK_OPS_CHANNEL=C0C34GCAR27          #resonate-notifications  (internal)
    SLACK_STATUS_CHANNEL=C0C3C6MDN9L       #resonate-os             (internal)

`SLACK_OPERATOR_USER` was **missing until today**, which meant nobody could
approve a change request and nothing said so out loud.
`scripts/slack_agent_bind.py --show` prints it; check it after any env edit.

The loop had been hung since 03:23Z — connected, no heartbeat for four
hours. Restarting it bare fixed it. There is no watchdog on the agent's own
heartbeat; if it hangs again nothing will notice.

---

## 2. THE BINDING, AS APPLIED

| What | Value |
| --- | --- |
| `slack.agent_channel` productive | `C0ADUMGQX8S` `#productive-resonate-outbound` |
| `slack.workspace_channel` productive | `C0BFUF4JRK9` `#replies-productive` — notifications only, **not** an agent channel |
| `slack.workspace_users` productive | 15 external `@<client-domain>.example.test` ids |
| `slack.internal_users` | 4 `@resonategroup.co` ids |

Verified: `C0BFUF4JRK9` resolves **unbound** for the agent, and **no notify
event type, digest, status message or briefing routes to `C0ADUMGQX8S`**.
The agent answers there; nothing else writes there.

Bots are in neither list deliberately. `handle` drops anything carrying
`bot_id`, so a bot cannot ask a question; listing one would only make a
reader think it could.

**First week is questions only.** Change requests from external people are
recognised and restated, the ticket goes to `#resonate-os` marked
`client-originated`, and the client is told it has been passed to the
Resonate team **with no timescale** — a test asserts the absence of ten time
words. No client has been invited to try it yet.

---

## 3. A CLIENT'S OWN SENDERS ARE THEIR OWN DATA

Operator decision, 2026-09-22. `#productive-resonate-outbound` may hear
Productive's authorized sender humans by name, their mailbox and seat
counts, daily capacity, campaigns carried, and bounce rate against the 2%
hard stop. The people sending for Productive **are Productive's own staff**
and half of them are in that channel.

It says "authorized senders", never "attested" — `attested`, `attestation`
and `warmup` remain refused in a client channel, so the vocabulary is
enforced rather than hoped for. `mailbox` and `seat` came off that list.

`sender_roster` is driven by the **attestation**, not by the account's own
`sender_id`. 225 mailboxes were imported from the provider carrying no
owner; 159 were authorized afterwards. That join is also what keeps the
three excluded identities out: an account with no attestation is
unreachable rather than reachable-and-filtered.

Live readback, which matches the handoff's own figures exactly:

    8 authorized people · 159 mailboxes · highest bounce 1.05%, lowest 0.61%
    kresimir 64 · bernarda 50 · ivan 13 · fran 12 · tomislav 11 ·
    bojan 6 · jakov 2 · luka 1

---

## 4. THREE THINGS FOUND THAT ARE NOT THE AGENT'S

### 4a. LinkedIn attestations can never resolve · `hr-` vs `li-`

**Measured on the live roster.** LinkedIn ownership attestations carry
account ids prefixed `hr-`; the LinkedIn account rows carry `li-`, same
numbers. **The overlap is zero.** So
`senderownership.attestation_for(workspace, "linkedin", "li-116968")`
returns `None` for every seat, and anything gating on a LinkedIn
attestation is failing closed and silently.

33 attestations, 32 seats, 0 matches.

The agent reports "seat ownership is recorded but does not match a seat, so
no seat count is claimed" rather than "0 seats", because zero would read as
"you have no LinkedIn sending" and that is false. **It does not join them by
stripping the prefix** — that would be inventing an identity mapping between
two id spaces, which is the thing an attestation exists to prevent.

Somebody has to decide which id space is canonical. Until then no LinkedIn
seat is provably authorized.

**And a consequence worth seeing before it is fixed:** several `li_*` roster
entries are *Resonate's own people*, not Productive's. Today they resolve to
nothing, so the client channel cannot name them. Fix the id mismatch without
a second filter and it will.

### 4b. `bison_mailbox_utilisation` runs but writes no heartbeat

It is in the process list and has no file in `work/heartbeat/`. Every
liveness check we have is blind to it. The agent reported it as not beating,
correctly, and that is the only reason it was noticed.

### 4c. One test invariant is red and it is not mine

`test_no_test_module_imports_a_provider_exception_by_name` flags
`tests/test_bison_sending_schedule.py:26` and
`tests/test_task235_dnc_cannot_stop_linkedin.py:20`. Both import
`ProviderError` by name; a reload replaces the class and the bound name
stops matching.

---

## 5. THE FAILURE DIFF THE OPERATOR ASKED FOR

Phase A's full-repo run — 10,873 tests, 113 failures — against the 85-row
`work/suite-2026-09-20-failures.txt` baseline: **33 new, 5 gone.**

Most are the verification-roles fixture drift that `bda06063` describes and
TASK-250 covers. **Two were mine and both were on the production path:**

> The agent's knowledge-pack cache, thread memory and request journal all
> wrote beside the queue **without calling `store.refuse_production_write`**.
> A test exercising any agent path could have written into real client
> state — the failure that once put fixtures in the real `replywatch.json`.

All three now ask, before `makedirs` rather than after, are in
`store.STATE_OVERRIDES`, are on the barrier checklist, and are **driven** by
`_writers()` rather than only source-matched. The journal is no longer
called `request-queue.jsonl`, because a second file whose name reads like
the queue is how the wrong override lands on the wrong file.

---

## 6. TESTS

433 green across the slack, invariant and workspace suites; the single
failure is 4c above.

    tests/test_slack_agent_scope.py                         41
    tests/test_slack_request_tickets.py                     45
    tests/test_a_client_can_never_reach_another_client.py   35
    tests/test_slack_agent_conversation.py                  25
    tests/test_slack_agent_numbers.py                       20
    tests/test_slack_knowledge.py                           20
    tests/test_slack_agent_readback.py                      19
    tests/test_slack_agent_loop.py                          14
    tests/test_slack_agent_cannot_act.py                    10

**Every module passes ALONE**, and that is the bar rather than the suite
total. Six classes drove a real turn without isolating the state, passed in
a 433-test run and failed on their own: a full run leaks one module's
environment into the next. `tests/slackbase.IsolatedState` wraps
`store.use_directory` and asserts the pack actually moved.

Offline by construction: no test reaches a model or a provider, and
`scripts/slack_agent_fake_client.py` stubs the provider so the fixture is
self-contained.

---

## 7. TWO THINGS THE LIVE RUN CORRECTED

**The number guard was too literal about percentages.** Asked how the
senders were doing, the answer was discarded for "unsupported number(s):
0.61%, 0.87%, 1.03%, 1.05%" — and the retry opened by pointing out that
those figures *are* in the readback under `bounce_rate_percent`, read off
the roster rather than derived. It was right. The comparison is numeric now
and a percent-named field admits the sign; a bare count of 2 still does not
license "2%".

**A guard whose trips cannot be diagnosed gets switched off.** The discarded
answer is now recorded in `work/slack-agent.jsonl` and never posted, and a
*number* trip gets one retry with the offending figures named. A *scope*
trip gets none — asking a model that has just named another client to try
again is asking it to leak more carefully.

---

## 8. WAITING, AND PHASE C

Waiting on the operator:

1. **Run the five client-mode probes live** from the operator's account in
   `#productive-resonate-outbound` before anybody is invited. Three were run
   locally through `--ask` and are in section 3 and the transcript; the
   operator asked to drive them personally.
2. **Decide the `hr-`/`li-` id space** (4a), which is blocking any provable
   LinkedIn seat authorization.
3. **Invite external people** to try the channel, when ready.

Phase C, not started: per-user roles beyond internal/client/unbound
(mapping a Slack id onto `workspaces.ROLES`), weekly-plan answers, and
proactive briefings beyond the 07:15 one.

Not built and deliberately so: nothing executes a ticket. The main session
drains `py -3 scripts/slack_requests.py --approved` and writes the outcome
back with `--done` or `--failed`; the agent reports it in the thread the
request came from.
