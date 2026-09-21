# Merge request — `slack-agent` Phase B

**For the main session.** Channel binding, client mode, change-request
tickets with operator approval, and the morning briefing.

Branch `slack-agent`, now merged up to `origin/master` at `6f1bda25`.
Worktree `../resonate-slack-agent`.

What it is: `docs/SLACK-AGENT-PHASE-B.md`. What follows is what you need to
decide.

---

## 0. PHASE A IS NOT ON MASTER

I was told Phase A was merged and live. It is not, and I checked three
places before saying so: `origin/master`, local `master`, and the main
checkout's working tree all lack `src/slackscope.py`. The work exists only
on `origin/slack-agent`.

`scripts/slack_agent_loop.py` in the main checkout HAS been updated to the
Phase A version, so something was copied across — but the five modules it
imports were not, and that checkout's loop cannot import. Worth a look
before anything is restarted from there.

Phase B is built on Phase A, so merging the branch brings both.

---

## 1. THE DIFF SINCE PHASE A

**New:**

    src/slackrequests.py                 recognise, restate, ticket, decide
    scripts/slack_agent_bind.py          the operator's binding tool
    scripts/slack_requests.py            YOUR queue - see section 3
    scripts/slack_agent_briefing.py      07:15 in #resonate-os
    scripts/slack_agent_fake_client.py   two synthetic tenants, offline
    docs/SLACK-AGENT-PHASE-B.md
    tests/test_slack_request_tickets.py                     38 tests
    tests/test_a_client_can_never_reach_another_client.py   23
    tests/test_slack_agent_loop.py                          14

**Changed:** `src/slackknowledge.py` (handoff discovery + `current_state`),
`src/slackagenttools.py` (three client tools, campaign membership,
`_campaign_rows`), `src/slackconversation.py` (the request flow),
`scripts/slack_agent_loop.py` (two extra posts, the decision path).

**`src/slackagentreadback.py` is still untouched.** Your `stages()` and
`batch_state()` landed on master and the `getattr` delegation now picks them
up — verified. The local fallbacks in `slackagenttools` are dead code as of
that merge and I have left them in place rather than delete them in the same
change as the merge; **they can go whenever you like.**

---

## 2. WHAT YOU HAVE TO SET

    SLACK_INTERNAL_CHANNELS=C0C34GCAR27,C0C3C6MDN9L
    SLACK_OPERATOR_USER=U07KWV94J0H
    SLACK_AGENT_MODEL=anthropic/claude-opus-5     (from Phase A)

`#resonate-notifications` and `#resonate-os` as internal, Zvonimir as the
operator. **`SLACK_OPERATOR_USER` is load-bearing**: with it unset, nobody
can approve anything, which is the safe failure but also a silent one if you
do not know to look. `scripts/slack_agent_bind.py --show` prints it.

`scripts/slack_agent_bind.py` deliberately does not edit `config/.env`: that
file holds credentials and a script that rewrites it is a script that can
lose one. It prints the line.

### Productive's channel is PREPARED, NOT BOUND

The operator said they would name it, and I have not guessed:

    py -3 scripts/slack_agent_bind.py --client productive \
        --channel <ID> --dry-run

ISSUE-005 in the register is still open on which Productive channel is
which — `#productive-resonate-outbound` (C0ADUMGQX8S) and
`#replies-productive` (C0BFUF4JRK9) both exist, and the register records
that the pairing is an operator decision nobody has made. Until one is
bound, every client channel resolves `unbound`.

---

## 3. THE REQUEST QUEUE IS YOURS TO DRAIN

There was no request queue to hand anything to, so Phase B is one:

    py -3 scripts/slack_requests.py --approved
    py -3 scripts/slack_requests.py --show <id>
    py -3 scripts/slack_requests.py --done <id> --note "what was verified"
    py -3 scripts/slack_requests.py --failed <id> --note "why not"

It is a **pull**. The agent writes tickets and executes none; you run
`--approved`, do the work through the gates that already exist, and write
the outcome back. The agent reports it in the thread the request came from.
A push would mean an agent that can make a privileged session act, and an
agent that can do that has the privilege whatever the diagram says.

`--done` refuses without `--note` and refuses a ticket that is not approved.
Write what was VERIFIED — a provider readback, the suppression list, the
approval fingerprint — because the requester reads it.

Ticket files are in `docs/requests/` and tracked in git. The journal beside
the queue is the machine copy; both are written together.

---

## 4. THE THREE THINGS WORTH ARGUING WITH

### 4a. A ticket's target is checked for ownership, and the refusal is deliberately uninformative

"Remove lead mole@another-client.test" in Acme's channel is refused with
*"I cannot find that in your workspace"* — **the same sentence a target that
exists nowhere gets**. An answer that distinguished them would confirm the
other client's record exists.

This closed a real hole. A ticket's target arrives in the message, not out
of the store, so none of Phase A's reading filters touched it: the ticket
would have been scoped to Acme and named somebody else's person, and
executing it would have reached another client's estate through a gate that
had checked the wrong thing.

`stop_account`, `add_lead` and `change_window` are exempt, and the reasoning
is in the code: none of them is a claim about an existing record.

### 4b. The knowledge pack no longer names a handoff

Phase A hard-coded `PRODUCTION-HANDOFF-2026-09-21-EVENING.md`. Your NIGHT
handoff landed the same evening and the pack went on serving the evening's
picture as current — the register's own recurring defect, in the module
written to avoid it.

Handoffs are now discovered and sorted newest-first, each section records
which document it used, and a new `current_state` section reads the newest
one's headline and its "waiting on the operator" list. **It matches that
heading from a list**, because the evening's was "TOMORROW'S FIRST THREE
ACTIONS" and the night's is "WHAT IS WAITING ON THE OPERATOR". If you rename
it again, add the new name to `WAITING_HEADINGS` or the briefing's third
sentence goes quiet.

### 4c. `slackagentreadback.blocked()` still counts bullets — STILL NOT FIXED

Reported in the Phase A merge doc, which you did not see because Phase A did
not merge. It walks the `## OPEN` section of the register and counts every
`- ` line: **the register has 10 issue rows, 6 open; `blocked()` reports
47.**

`slackagenttools.open_issues()` parses `### ISSUE-nnn` and is what the agent
uses, so the agent is correct today. `blocked()` has other callers. It is
your file and I have not touched it.

---

## 5. VERIFY BEFORE MERGING

    py -3 -m unittest tests.test_slack_agent_loop \
        tests.test_slack_request_tickets \
        tests.test_a_client_can_never_reach_another_client \
        tests.test_slack_agent_scope tests.test_slack_agent_conversation \
        tests.test_slack_agent_cannot_act tests.test_slack_agent_numbers \
        tests.test_slack_knowledge tests.test_slack tests.test_slack_route \
        tests.test_web_slack tests.test_workspaces tests.test_web_settings

**328 green.** Then, reaching no live API:

    py -3 scripts/slack_agent_fake_client.py --build
    py -3 scripts/slack_agent_fake_client.py --interview      # 0 problems
    py -3 scripts/slack_agent_briefing.py --preview
    py -3 scripts/slack_agent_bind.py --show

The full-repo run from Phase A: **10,873 tests, 113 failures, none in any
Slack module** — they are the enrichment/e2e/preproduction fixtures your own
`bda06063` describes, and TASK-250 is the fixture work for them.

### The mutation run is the part to read

Fifteen mutations. Two found uncovered guards — the loop's internal-channel
check on decisions, and the clearing of a pending restatement — and both now
have tests.

The third finding was about method. **The first mutation run reported every
mutation caught, and was worthless**: the new ownership check had broken the
ticket fixture, so the suite was already red and every mutation "failed" it.
A mutation run against a red suite proves nothing. The fixture was fixed,
the suite verified green, and the second run gave one or two named failures
per mutation instead of twenty.

---

## 6. WHAT PHASE B DOES NOT DO

- **No client channel is bound.** One command, your call.
- **Nothing executes a ticket.** That is section 3, and it is yours.
- **Per-user roles are still internal / client / unbound.** Mapping a Slack
  user onto `workspaces.ROLES` is Phase C.
- **No weekly plan answer.** Phase C.
- **The briefing reads heartbeats from wherever it runs.** Run it from the
  production checkout or it will report every monitor silent, correctly and
  uselessly.
