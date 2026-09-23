# Slack agent — handoff, 2026-09-23 afternoon

Supersedes `SLACK-AGENT-HANDOFF-2026-09-23-MORNING.md` and everything before
it. Written to the test CLAUDE.md sets: a fresh session on another machine,
with a clone and the secrets supplied separately, should be able to read
this and say what happened and what to do next.

**Branch `slack-agent` at `2619f536`**, pushed and verified. Master is
`51dfa991` plus whatever has landed since; this branch was merged onto
master at `75038ca4` mid-session, so it is current.

**Phase D2 (`edb9146f`) was merged by production today and the agent loop
was restarted onto it** — pid 34924, code written 12:16, verified. The queue
page cap is live.

---

## 1. THE FOUR STACKED MERGE REQUESTS, IN ORDER

They stack. Each assumes the one above it. **Take them in this order or
take them together; do not cherry-pick the middle.**

    1  docs/MERGE-REQUEST-SLACK-AGENT-PHASE-D3.md   2afc2020 .. b428fea9
       The two-post follow-up offer: one post when the batch's first
       provider-confirmed send lands, one on the first reply a PERSON
       wrote, then stop.

    2  docs/MERGE-REQUEST-SLACK-AGENT-PHASE-D4.md   0e8133a8 .. e9a6e848
       account_status - "what is happening with <domain>". Reworked onto
       the operator's write-back decision: reads the ledger, provider is a
       periodic workspace witness, never a per-account call.

    3  (no separate doc)                            94725a3d
       Reply counting that survives production's one-row-per-reply fix.
       Small, and it belongs with 2.

    4  (no separate doc yet)                        2619f536
       weekly_report - accounts first, then emails. Phase D item 3 plus
       the operator's additive item 3.

**Nos. 3 and 4 have no merge-request doc of their own.** Their commit
messages carry the full argument; the operator asked for the handoff before
those docs were written. If your process needs a doc per increment, they are
the two to write first.

### 1a. The ordering rule that matters on merge

**When D3 merges, restart `slack_followup_loop.py` AND `slack_agent_loop.py`
in the same step.** D3 changes `OFFER_NOTICE` to promise two posts. Merging
it without restarting leaves the promise saying two while the running
process makes one — which is this module's original fault, a promise
outrunning its mechanism, wearing a new hat.

Until D3 merges, starting the follow-up loop from master is coherent: the
one-post offer, and master's `OFFER_NOTICE` still promises exactly one.

---

## 2. PHASE D, WHERE IT STANDS

    1. Croatian reply + five probes   DONE except the send - see §4
    2. proactive client updates       DONE, merge request 1
    3. weekly client report           DONE in figures, merge request 4.
                                      The Monday 08:00 schedule, the
                                      30-minute preview and the PDF are
                                      NOT built.
    4. positive replies to client     BLOCKED, and not on effort - see §3
    5. question catalogue, next ten   open
    6. multi-workspace readiness      open, and it is the next increment
    7. internal briefing additions    open
    8. CLIENT-PORTAL-DESIGN.md        open, last for a reason

### 2a. Item 3 is only half done

`weekly_report` produces the figures, accounts first. What does not exist:
the Monday 08:00 local schedule, the preview into `#resonate-os` thirty
minutes earlier, and the PDF. **`src/clientreport.py` already renders PDFs**
— 55KB of it, templates and sections — and takes a `data` dict it does not
gather. Its data comes from `src/web/api.py`'s analytics layer, which is not
this session's to rewire, so the agent's figures were built in the agent's
layer. Whoever does the PDF step should decide whether to feed
`clientreport.build()` from `weekly_report` or leave them separate; they
answer the same question in two shapes today.

---

## 3. WHY ITEM 4 IS BLOCKED, AND IT IS THE FINDING OF THE AFTERNOON

Item 4 posts positive replies into a client channel. **On today's ledger it
would post an autoresponder.**

The accounts-first report reads `positive: 1` for Productive. The operator's
re-run of 2026-09-22 concluded **0 positive of 14**. Same day, so one is
stale, and it is the ledger.

Traced and confirmed against the provider:

    stored     jennifer-bagley, campaign 491, `positive`
               by classifier `rules-3` at 18:35 on 2026-09-22
               - three hours before 4af4f982 changed the rules
    current    assistant_redirect, which is automated
    provider   automated_reply flag on that row: true
    text       "Jennifer's inbox can get a little extra at times, so her
                amazing Executive Assistant Rose is helping keep things
                running smoothly"

**It is the EA reply** — the one the whole reply-classification policy was
written about. The re-run's verdicts were never written back.

### 3a. And the guard that would catch it does not exist

`replies.VERSION` is still `"rules-3"` — **the same string the stale event
carries.** The rules changed and the version did not, so a stored verdict is
indistinguishable from a fresh one by inspection.

The operator has since specified the fix (§5). Until it lands:

- `weekly_report` reports the positive count **with a caveat naming this
  reply**, rather than suppressing the figure — suppressing would hide the
  disagreement.
- `tests/test_the_report_counts_accounts_before_emails.py` asserts
  `replies.VERSION == "rules-3"`, so **the day it is bumped this test fails
  loudly** and somebody revisits the caveat instead of letting it outlive
  the problem.

### 3b. What the agent side still owes once production acts

The operator's item 3 of that decision — *"any reader treats a verdict whose
version is older than `replies.VERSION` as stale and re-classifies before
counting"* — is **not built on the agent side**, and there is a concrete
obstacle:

**`account.replies()` does not project `classifier` or
`provider_event_id`.** It returns contact_key, channel, at, type,
classification, positive. Without the version the reader cannot tell stale
from fresh, and without the provider id it cannot find the reply text to
re-classify.

Two ways, and the first is better: **widen that projection by two fields**
(it is a shared module, so production's), or have the agent read the raw
events itself — which is exactly the second walk of the event log
`account.py`'s own docstring argues against. The join itself is proven: the
event's `provider_event_id` is `emailbison:<uuid>:classified` and that uuid
matches `bison.fetch_replies()` rows' `uuid`; that is how the Jennifer/Rose
reply was traced.

---

## 4. THE CROATIAN CORRECTION IS DRAFTED AND STILL UNSENT

**Draft `Dr0C3XFG2CCR`**, in Bruno's thread `1790061486.125249` in
`#productive-resonate-outbound`.

**It cannot be sent from here.** That channel is Slack Connect (externally
shared) and the MCP token is refused: `mcp_externally_shared_channel_restricted`.
Only the app can post there. **A person has to send the draft.**

What it says: the 14:42 list of 09-22 marked every one of 69 domains
`bez slanja u zadnjih 7 dana` on a day those mailboxes sent 494; the domain
names, 159 mailboxes and 8 senders were correct; only the recency markers
were wrong; the fault is fixed. **That last clause is now true in
production** — D2 is merged and the loop restarted onto it.

**Do not send D1 §5 verbatim instead.** Its flags were generated while
campaign 491 was still unreadable, so some are wrong in the same direction
as the message they would correct.

---

## 5. WHAT PRODUCTION OWES, AND WHAT EACH ONE UNBLOCKS

Ordered by what is blocked behind it.

1. **The event-ledger write-back.** Four event kinds — provider-confirmed
   sends, bounces, replies, HeyReach requests/accepts — written back on
   every watcher readback, idempotent per provider row id. **No new event
   type and no schema change**: `push_marked`, `email_delivered`,
   `linkedin_connected`, `reply_received`, `reply_classified` all exist.
   *Unblocks:* account status and accounts-first reporting, both of which
   are nearly silent today. Live measurement: the ledger holds **1**
   confirming event against **494** provider-confirmed sends, so the report
   currently returns `unanswerable 1530`.
2. **`replies.VERSION` bumped on every rules change**, with a test hashing
   the rule tables so it cannot drift again. *Unblocks:* telling a stale
   verdict from a fresh one, which unblocks item 4.
3. **Re-run the classifier over both days and write the verdicts back** as
   new `reply_classified` events carrying the version. *Unblocks:* the EA
   reply stopping being a stored `positive`.
4. **Widen `account.replies()` by `classifier` and `provider_event_id`**
   (§3b). *Unblocks:* the agent doing its half of stale-verdict handling
   without a second walk of the event log.
5. **Start `scripts/slack_followup_loop.py`** as a monitor, bare, one
   instance. *Unblocks:* the follow-up offer existing at all — it is
   switched off by construction until the deliverer beats, and there is
   still no `work/heartbeat/slack-followup.json`.
6. **Merge D3 and D4, restarting both loops in the same step** (§1a).
7. **Fix `account.replies()` one-row-per-reply at source**, and check the
   digest, the summary and the hard-stop math for the same double count.
   The agent's counting is already shape-aware and needs nothing.
8. **Send the Croatian correction draft** (§4).

---

## 6. THE NEXT INCREMENT: A SYNTHETIC SECOND CLIENT

Phase D item 6, multi-workspace readiness: a synthetic second client, all
client tools and the weekly report for both, **zero cross-visibility**.

It is the right next one for three reasons:

- **It does not depend on the write-back.** Every other open item does, or
  is design work.
- **The isolation properties are already written and already tested
  one-sided.** `account_status` asserts that another client's domain and a
  domain nobody has return the identical note, word for word, because the
  difference between them is the leak. `weekly_report`, `lead_counts` and
  `lead_in_campaign` have the same shape. A second workspace turns those
  from one-sided assertions into real two-sided ones.
- **Real second clients already exist in Slack**: two live client channels
  (named in the workspace policy, not here) carry real client traffic.
  **Binding a real one is an operator decision,
  not this session's**, which is exactly why the synthetic one is the right
  vehicle — it proves the isolation without touching a real client's data.

Start from `work/workspaces.jsonl`'s shape and the `_workspace_for` /
`_records` pinning, which is where every client tool's scope is decided.

---

## 7. THE THINGS THIS SESSION LEARNED THAT ARE NOT IN A DIFF

- **A worktree's `work/` holds almost nothing** — 4 files against
  production's ~20, no `senders.jsonl`, no `queue.jsonl`. So
  `slack_agent_loop.py --ask` run from a worktree answers **confidently
  empty**: asked for Productive's sending domains it said "no authorised
  domains or senders at all" where production has 69 and 159. Copy the
  stores the answer needs to a scratchpad and point `WORKSPACES`,
  `SENDERS`, `CAMPAIGNS` at the copies — read, never write. `queue.jsonl`
  is 300 real companies and 92 real contacts; copy it only when needed.
- **The full-repo `unittest discover` is not green on master and has not
  been**: 71 failures and 35 errors over ~11,500 tests, today, with no
  changes present. Run file by file they pass. **The operator has said that
  baseline is infra's — do not touch it** — but never read a green
  file-by-file run as a green suite, and always diff failure sets **by
  name**, never by count.
- **Four defects this session, one shape.** A fixture that mocked the layer
  the defect lived in; a list read as a mapping; a field that could never
  vary; a count of events read as a count of things. All four were found by
  reading the code being called, or by comparing an answer to the provider.
  None was found by the suite.

---

## 8. THE RULES THIS SESSION WORKED UNDER

Unchanged, stated by the operator, verified for every commit above:

- Never merges to master and never pushes to it. Delivery is a merge-request
  doc in `docs/` plus one line in `#resonate-os` (`C0C3C6MDN9L`).
- Never edits `config/.env`, `work/`, `src/providers/*` or
  `scripts/*_watch_loop.py`. **Verified**: this session's diff touches
  `src/slackagenttools.py`, `src/slackagentreadback.py`,
  `src/slackfollowup.py`, `src/slackconversation.py`,
  `scripts/slack_followup_loop.py`, test files and docs. Production's
  `work/` was **read and copied**, never written.
- A merge request per increment; a handoff before context runs out.
- Adversarial probes offline only.
- **One instruction was declined**: a request to merge D1/D2 to master and
  restart via `start_monitors.py`. D1 and D2 were already on master,
  `start_monitors.py` did not exist on master at the time, and the message
  referred to "the agent session" in the third person — it read as
  addressed to production. It was reported rather than acted on, and
  production merged D2 itself shortly after.
