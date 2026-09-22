# The Slack agent — Phase B, 2026-09-21

Channel binding, client mode, change requests with operator approval, and a
morning briefing. Phase A gave the agent knowledge and a voice; Phase B
gives it a second audience and a way to turn "can you remove this lead" into
something a person decides.

It still cannot change anything. That is structural and unchanged: the
import graph has no write path, and a ticket is a record of a request rather
than an instruction.

Phase A is `docs/SLACK-AGENT-PHASE-A.md`.

---

## 1. BINDING

Three policy keys, set by the operator, read by nobody else:

| Key | What it binds |
| --- | --- |
| `slack.agent_channel` | the channel where the agent answers AS this client |
| `slack.workspace_users` | Slack user ids that are this client's people |
| `slack.internal_users` | Slack user ids on the Resonate team |

Internal channels and the operator come from the environment, because
neither belongs to a workspace:

    SLACK_INTERNAL_CHANNELS=C0C34GCAR27,C0C3C6MDN9L   #resonate-notifications, #resonate-os
    SLACK_OPERATOR_USER=U07KWV94J0H                   Zvonimir

`scripts/slack_agent_bind.py` is the only thing that writes a binding:

    --show                              every binding, and where each came from
    --internal C0... C0...              prints the env line (writes no .env)
    --operator U...                     prints the env line
    --client <slug> --channel C0...     binds one client channel
    --unbind <slug>                     removes one

`--client` refuses more than it accepts, and each refusal is a disclosure it
is preventing rather than a validation nicety:

- **a `#name` instead of an id.** `slack.post` resolves no names — it passes
  the string to `chat.postMessage` — so a name that looks right and is not
  would bind the agent to somebody else's room.
- **a channel that is already internal.** A channel cannot be both the
  team's and a client's.
- **a channel already bound to another workspace.** Silently taking it over
  would be worse than refusing.
- **anything, without `--dry-run` first being available.** The dry run
  prints the workspace, the channel, the name Slack gives that id, and a
  sentence saying exactly what the agent will then be willing to say in
  there.

After writing, it **reads the binding back** and says so if the readback
disagrees.

### Productive is prepared, not applied

    py -3 scripts/slack_agent_bind.py --client productive \
        --channel <THE ID YOU NAME> --dry-run
    py -3 scripts/slack_agent_bind.py --client productive \
        --channel <THE ID YOU NAME>

Not chosen here, deliberately. ISSUE-005 in the register is still open on
exactly which Productive channel is which — `#productive-resonate-outbound`
(C0ADUMGQX8S) and `#replies-productive` (C0BFUF4JRK9) both exist and the
register says the pairing is an operator decision. Guessing between them is
the one mistake this module is built to prevent.

Until it is bound, every client channel resolves `unbound` and the agent
gives generic answers there. That is the intended state, not a gap.

---

## 2. CLIENT MODE

The five questions, answered against a fake client before anything real was
bound:

| Question | What answers it |
| --- | --- |
| which cadence is active | `cadence_detail` — email steps and the LinkedIn graph |
| how many senders are sending for us | `sender_summary` — counts, never names |
| is <person or domain> in a campaign | `lead_lookup` / `account_lookup` |
| what went out this week | `activity_this_week` |
| what replies came in | `replies` |

**`sender_summary` answers without the roster.** The estate is real people
whose names live in a gitignored file. A campaign row carries
`provider_account_id`, so "how many senders are sending for us" is answerable
as a count of distinct sending accounts with no name and no address in it.

**`activity_this_week` does not report a lifetime counter as a weekly one.**
The provider's `emails_sent` is lifetime. The weekly figure is counted from
queue rows carrying a `sent_at` inside the window, and the lifetime counter
is reported beside it and labelled. Reporting one as the other is the same
class of error as reading `active` as a send.

**A campaign that cannot be read makes the total a floor, not a zero.**
`_sent_since` returns `None` rather than `0` when the queue refuses, and the
answer says how many campaigns it could not read.

### Testing it on nobody

    py -3 scripts/slack_agent_fake_client.py --build
    py -3 scripts/slack_agent_fake_client.py --interview

Two synthetic workspaces — `acme-test` and `rival-test` — in a throwaway
state tree, with a stubbed provider so the fixture reaches no live API. The
interview runs the five questions and five probes, and fails if a probe
finds the rival's slug, contact, campaign, or any internal vocabulary in a
reply. It reports **0 problems**.

The probe checker had to be made precise before it was useful. Its first
version grepped for "rival" and flagged a correct answer: asked about
`rival-secret.test`, the agent said "there is no account matching
rival-secret.test in your store", which discloses nothing. Repeating
somebody's own question back to them is not a disclosure, and a probe that
cannot tell the difference trains whoever reads it to ignore it.

---

## 3. CHANGE REQUESTS

Six kinds, recognised from ordinary sentences:

    remove_lead       remove lead X (from campaign Y)
    stop_account      stop contacting Y
    change_copy       change the connection message / step N copy of cadence Z
    pause_campaign    pause campaign N
    add_lead          add a lead
    change_window     change a sending window

### Two turns, and nothing is written in the first

    turn 1   restate the exact intent. Nothing recorded.
    turn 2   the requester confirms IN THE SAME THREAD. Ticket written.

The restatement is the point:

> **Remove a lead from outreach** for acme-test. Lead: ada@northwind.test.
> Campaign: 9001. If approved, this is what happens: add the contact to this
> workspace's suppression list, then stop the lead at the provider on BOTH
> channels through the existing stop verbs with their fail-closed readbacks.
> The queue record is dropped with a reason, never deleted. Nothing is done
> until Zvonimir approves it. Confirm and I will raise it.

A request that cannot be pinned down becomes a **question**, never a vague
ticket: "I still need which person — their email address."

A confirmation only counts against an open restatement in the same thread,
it is cleared when the ticket is raised, and it expires after an hour.

### The ownership check — the hole Phase B had to close

A ticket's target comes from the **message**, not from the store, so no
reading filter touches it. "Remove lead mole@another-client.test" typed in
Acme's channel would have produced a ticket scoped to Acme naming somebody
else's person, and executing it would have reached into another client's
estate through a gate that had checked the wrong thing.

`check_ownership` refuses it — and **the refusal is identical whether the
target belongs to another client or to nobody at all**:

> I cannot find mole@another-client.test in your workspace, so I have not
> raised anything.

An answer that told those two cases apart would confirm the other client's
record exists, and that confirmation is the disclosure.

`stop_account`, `add_lead` and `change_window` are deliberately exempt: a
client may pre-emptively name a domain they never want contacted, may give
us somebody new, and may change their own window. None is a claim about an
existing record.

### The gate

`ACTION REQUIRED` goes to the internal channel with `approve <id>` /
`reject <id>`. **Only `SLACK_OPERATOR_USER` counts.** Not an admin, not
somebody in the internal channel, not the requester however senior they are
at the client. An attempt by anybody else is **recorded on the ticket** and
refused — somebody trying to approve their own request is what the person
reading the file later needs to see.

An `approve <id>` in a *client* channel is not a decision at all: the loop
does not let it reach the decision path, and it is answered with a sentence
saying where approvals happen.

With no operator configured, nobody can approve. That is the safe failure.

### The handoff

    py -3 scripts/slack_requests.py --approved     # what to execute now
    py -3 scripts/slack_requests.py --show <id>
    py -3 scripts/slack_requests.py --done <id> --note "what was verified"
    py -3 scripts/slack_requests.py --failed <id> --note "why not"

A **pull**, not a push. The agent writes tickets and never executes one; the
main session drains the queue and writes the outcome back; the agent reports
it in the thread the request came from. The alternative is an agent that can
make a privileged session act, and an agent that can do that has the
privilege whatever the diagram says.

`--done` requires `--note` and refuses a ticket that is not approved.

Two files are written together: `docs/requests/<date>-<id>.md` for a person,
and an append-only journal beside the queue for the machine. The latest
journal row per id wins.

---

## 4. THE MORNING BRIEFING

`#resonate-os`, 07:15 local, three sentences: what happened, what is next,
what needs the operator.

    py -3 scripts/slack_agent_briefing.py --loop --interval 300
    py -3 scripts/slack_agent_briefing.py --preview

**The hour is derived, not hard-coded.** It fires `MINUTES_AFTER_DIGEST = 15`
after `DIGEST_HOUR`, which is 5 UTC today and **moves to 6 on 2026-10-25**
when CEST ends. Hard-coding 07:15 would have put the briefing an hour away
from the digest it is supposed to follow, on a date the handoff already
names.

One per calendar day, recorded in the agent's own log. A loop that starts
three hours late records a **missed** briefing rather than posting a stale
one.

A real preview:

> Since last night: 489 is still the only thing actually sending — 3 emails
> out of 8 queue rows against 5 leads — while 491-498 are bound to the
> provider but paused, so the 151 enrolled leads behind them have had 0
> sent […]
>
> Zvonimir, five things are yours: activate 491-498 (one line, 151 enrolled
> leads behind it), approve the re-engagement copy […]

Every figure passes the same number guard as any other answer.

---

## 5. THE KNOWLEDGE PACK FOLLOWS THE NEWEST HANDOFF

Phase A named `PRODUCTION-HANDOFF-2026-09-21-EVENING.md` in a tuple. Within
hours a NIGHT handoff superseded it — "151 leads are enrolled and none of
them can be sent to" — and the pack went on serving the evening's picture as
current. That is the register's own recurring defect, committed by the
module written to avoid it.

Handoffs are now **discovered and sorted**, newest first, and a section that
needs one scans in that order and records which document it used. Sorting
took two cases that are not the same: a handoff with **no** part suffix is
the day's base document and sorts oldest within its day; an **unknown** part
sorts newest.

A new `current_state` section carries the newest handoff's headline, what is
waiting on the operator, and the monitors it expects to be running. The
"waiting" heading is matched from a list, because handoffs do not use one
name for it — the evening's was "TOMORROW'S FIRST THREE ACTIONS", the
night's is "WHAT IS WAITING ON THE OPERATOR".

The pack cache and the thread memory now resolve **per call, beside the
queue**, like every other state file here. A fixed path meant the fake-client
harness read the real pack; the bug was in the harness that time, and it
would not have stayed there.

---

## 6. TESTS

    tests/test_slack_request_tickets.py                     38
    tests/test_a_client_can_never_reach_another_client.py   23
    tests/test_slack_agent_loop.py                          14
    tests/test_slack_agent_scope.py                         41
    tests/test_slack_agent_conversation.py                  25
    tests/test_slack_agent_cannot_act.py                    10
    tests/test_slack_agent_numbers.py                       16
    tests/test_slack_knowledge.py                           20

328 green including the Slack and workspace suites.

**Fifteen mutations, and the run found three things.**

Two guards were uncovered: the loop's internal-channel check on decisions
(so `approve <id>` in a *client* channel would have become a live decision
attempt) and the clearing of a pending restatement (so a second "yes" would
have raised a second identical ticket). `tests/test_slack_agent_loop.py` and
two new ticket tests cover both.

The third finding was about the method rather than the code. The first
mutation run reported every mutation "caught" — because the suite was
**already red**: the new ownership check had broken the ticket fixture,
which had no estate for its workspace, and every mutation was being measured
against a suite that failed anyway. A mutation run against a red suite
proves nothing. The fixture now carries an estate, the suite was verified
green first, and the second run produced precise results: one or two named
failures per mutation instead of twenty.
