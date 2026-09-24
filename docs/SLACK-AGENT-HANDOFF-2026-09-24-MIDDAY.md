# Slack agent — handoff, 2026-09-24 midday

Supersedes `SLACK-AGENT-HANDOFF-2026-09-24-MORNING.md` and every earlier one.
Written to the test `CLAUDE.md` sets: a fresh session on another machine,
with a clone and the secrets supplied separately, should be able to read
this and say what happened and what to do next.

**Branch `slack-agent` at `a87e787c`, pushed and verified.** It merges
master at `522495b3`; master has since moved to at least `d6a719c2` —
fetch and check before writing anything.

---

## 1. THE HEADLINE, AND IT IS NOT THE LATENCY

**THE BRANCH WAS NEVER GREEN, AND THE LAST HANDOFF DID NOT SAY SO.**

    full suite, pre-merge tip 20586a63      136 failures
    full suite, this branch a87e787c        123 failures

Nothing in the morning handoff is untrue about it; it simply never ran the
whole suite, and "hygiene 13 of 13, the slack modules green" reads exactly
like a green suite to the next reader. It was read that way here for most
of a session.

**Compare these as SETS BY NAME, never as counts.** Against the 136:
**3 introduced, 16 fixed.** All three introduced are MASTER'S — verified
against master alone at `d6a719c2` — where `heyreach.stop_lead` is enabled
by one commit and asserted unsupported by two tests, plus a linkedin
field-name test. Ten of the sixteen fixed are `test_what_are_we_working_on`.

`scripts/suite_verdict.txt` is TRACKED and is written by `run_suite.py` in
whichever checkout runs it. The copy in git is production's from another
day. **Reading it as this branch's verdict is a mistake this session made**
before catching it, and it reported 110 failures from another machine.

---

## 2. WHAT SHIPPED — `docs/MERGE-REQUEST-2026-09-24-LATENCY.md`

Read that for the detail. In one table, measured by
`scripts/measure_readback_fanout.py`, whose BEFORE column is
`PROVIDER_FANOUT=1` and `READBACK_TTL=0` — the old path on this tree, not
a revert:

| | before | after |
|---|---:|---:|
| a four-tool turn | 198.65s | **17.69s** (146 → 60 calls) |
| `working_on`, the broad-question route | 43.57s | **5.44s** |

The BEFORE column reproduces the live replay without being fitted to it —
`sends_today` 21.78s against **21.72s measured live**. **It is still a
mechanism measurement**: a stub has no tail, and p50/p95 must come from the
replay against the real provider.

Three pieces: a readback cache scoped to one turn, bounded parallel
per-campaign reads (`_fan_out`, six at a time, results in the caller's
order), and broad questions planning one tool before the planner model is
asked.

---

## 3. THE LESSON LIST IS AT NINE, AND THE NINTH IS DIFFERENT

The eight before it are all "a test can be green because it is
unfalsifiable." The ninth is about the CHECKING rather than the check:

    a grep for '^FAIL:' against a RUNNING unittest log

Unittest prints those blocks only in the end-of-run summary. The command
returned 0 for thirty minutes and could not have returned anything else,
and **absence of a signal was reported as a green signal** — twice, in
writing, to the operator. The cache increment was called verified on that
basis and was carrying thirty failures.

### 3a. And the failure it hid is worth its own paragraph

The readback cache was first built process-global with a 60-second TTL.
Correct in production — one loop, one turn at a time — and wrong in a
suite, where a test stubs the provider, calls a tool, restubs and calls
again and gets the first stub's answer. **Not one of the 154 failures
named the cache.** They said

    AssertionError: 'unreadable' != 40

in a module about scheduling horizons, three layers from the cause. Every
targeted module run passed beforehand, because each module is green alone
and red only after its neighbour.

Fixed by SCOPE, not a flag: `readback.turn()`, opened by
`slackconversation.respond`. Outside a turn `cached` is a pass-through.
**This gives up nothing measured** — re-measured after the fix at the same
11.2× and the same 86 calls saved — because every repeat the cache removes
is inside one turn. It also closes the staleness risk outright: the next
question starts cold.

The proof that the scoping is real came free: the measurement harness was
ported without opening a turn and printed **146 provider calls in both
columns**, "0 saved by the cache". The comment at that call site says so,
because the next person to measure this will make the same mistake.

### 3b. The eighth, from the same session

`tests/test_fixture_hygiene.py` collected **13 of 17** when run directly,
because master's new `TestTheExemptionStaysNarrow` landed below
`unittest.main()`. `-m unittest` imports first and ran all 17. Green both
ways, wrong in one. The block is at the end of the file now.

---

## 4. WHAT PRODUCTION OWES — ONE IS NEW AND IT IS THE BIGGEST

### 4a. A CLIENT CHANGE REQUEST CURRENTLY REACHES NOBODY

`CLIENT_CHANNEL_GAG` returns at `slackconversation.py:1406`. `_raise_ticket`
is at **1454**. So in a client channel the turn returns before the ticket
is written, and `scripts/slack_agent_loop.py:254` writes a `kind: gagged`
row to `work/slack-agent.jsonl`, emits one line to stdout, and returns.
**No Slack post, no ticket, no internal notification.**

The question catalogue names the highest-severity shape in the whole corpus
as a client change request — a reply-stop complaint with four question
marks. Today that produces a log line. The gag was set to stop the agent
saying something wrong to a client; it also stopped the operator finding
out the client asked.

It is also **31 of the 123** — `test_slack_request_tickets`, 12 of them
naming `gagged` directly.

**The cheapest fix is to let the ticket path run before the gag returns**,
because a ticket is an internal write and not client-visible text. That is
production's decision and it is the gag's fourth outstanding item.

### 4b. The three from the morning handoff, re-checked rather than assumed

- **`rules-4`** — `replies.VERSION` is `"rules-3"`; no `RULE_HASH`,
  `RULES_HASH` or `RULE_FINGERPRINT` exists in `src/`. `positive_confirmed`
  is 0 and Phase D item 4 correctly posts nothing. **STILL BLOCKED.**
- **The ledger write-back** — production's own `work/queue.jsonl` carries
  **one** confirming event across **1,543 records**: a single `push_marked`,
  zero `email_delivered`, zero `linkedin_connected`. `_ledger_carries_sends`
  needs `touches >= provider_sent // 10`, so one cannot clear any threshold
  above ten sends. **STILL BLOCKED**, established with no provider call.
- The Slack file-upload route, the briefing loop's supervision and the
  Monday loop are unchanged. `src/providers/*` remains forbidden here.

### 4c. Whether the gag is even live is untested in production

No client question has been asked since it was set: the agent log's last
three client answers are 2026-09-23T11:28–11:51, which ARE the three faults
that caused it. There are **zero** `kind: gagged` rows. So nothing has
exercised it, and a merge is not a deploy — the loop imports at start and
does not reload.

---

## 5. TWO THINGS THAT DO NOT NEED BUILDING

**Check the premise before building to it**, which paid twice more.

1. **Item 5 is already built.** `meetings_booked` and `promises` are
   registered tools. `slackpromises.scan()` already takes `window_days`
   (default 10; the operator said 7 — that is an argument, not a build).
   `account_status` already threads `ledger_ok` and reports `unanswerable`
   separately. What remains of item 5 is a decision about the window and
   the ledger blocker in 4b.

2. **`_forward_window` was a third provider read path in nobody's budget** —
   `bison.sending_schedule` direct, three days by ten campaigns, thirty
   serial live HTTPS requests, bypassing `slackagentreadback` entirely.
   Found by stubbing the other two reads and profiling `weekly_plan`
   anyway, when it still cost 3.4s and still hit the network. Routed and
   fanned out; that is the 81.6s → 6.8s row.

---

## 6. BEFORE ITEM 3 IS BUILT: THE ARCHIVE HOLDS CREDENTIALS

The missed-mention sweep reads `work/slack-history/`. That archive contains,
by shape and counted without printing a value:

    8   sk- API keys
    4   slack tokens
    6   password: <value>

all in one channel file. `work/` is gitignored, so none of it is in git, and
the question catalogue already drops credential-marked messages — **but the
sweep reads the raw archive, not the catalogue.** Redact at READ, before the
first comparison, not before the report.

The archive also predates the agent. It starts months before
`work/slack-agent.jsonl`, which begins 2026-09-21T18:41, so a sweep that
does not window to the agent's own lifetime will report every pre-agent
mention as a missed one. A first pass found 32 messages addressing the
agent across 11 channel files, and almost all of them are older than the
agent — that number is **not** a missed-mention count and must not be
reported as one.

---

## 7. THE MEASUREMENT THAT IS STILL OWED, AND WHY IT IS CIRCULAR

The operator's target is **p50 under 15s, p95 under 30s IN CLIENT SCOPE.**
Client scope returns gagged at 0.0s, so a live replay measures the gag. And
the gag is not to lift until the latency is fixed.

**The replay is the way out, because it posts nothing.** Lifting the gag
inside the replay process is not lifting it in production — there is no
Slack write on that path, and provider reads are the only live thing about
it. `scripts/slack_agent_replay.py` needs a `--lift-gag` flag; it is not
written yet, and it is the next thing.

`scratchpad/replay_after.sh` is drafted and NOT RUN: it copies production's
`work/` rather than pointing at it (thirty-three replayed turns write thread
memory) and points `WORKSPACES`, `SLACK_THREADS` and the rest into the copy,
because **the worktree's own `work/` is stale and thin and a client probe
run there resolves UNBOUND.** Production's log now holds **33** questions
since 2026-09-21, one more than the morning's 32.

---

## 8. THE REPLAY HARNESS IS FIXED, AND IT HAD SCORED NOTHING

`--catalogue` matched `- "quoted line"`. The catalogue has only ever used
blockquotes in emphasis, so the flag **added zero questions to every run
that passed it** and the run printed a plausible count either way. It now
parses 27 phrasings, joins the one that runs onto a second line, keeps
back-to-back ones apart, and **exits non-zero when it parses none**.

A seventh check, `subject`: does the answer name the thing the question
asked about? `numbers` reads the turn's own guard, which fires on a figure
ABSENT from the material and structurally cannot fire on a figure that is
present, correct, and answers a different question. The first row of the
2026-09-23 replay is exactly that and scored clean on all six. `n/a` where
no subject is extractable, never `pass`.

---

## 9. WHAT TO DO NEXT, IN ORDER

1. `--lift-gag` on the replay harness, then the live replay, then post the
   real p50/p95 against the 24.3s / 132.3s baseline. §7.
2. Item 3 — the missed-mention sweep, with §6's two constraints, and
   **report the count before building anything.**
3. Item 5's window decision (10 days or 7), which is an argument. §5.
4. Items 3b/4 — client deliverables, the Monday dry run with the PDF.
5. Raise 4a with production. It is larger than anything on this branch.
