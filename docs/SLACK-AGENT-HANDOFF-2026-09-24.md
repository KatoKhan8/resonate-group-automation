# Slack agent — handoff, 2026-09-24

Supersedes `SLACK-AGENT-HANDOFF-2026-09-24-MORNING.md` and every earlier one.
Written to the test `CLAUDE.md` sets: a fresh session on another machine,
with a clone and the secrets supplied separately, should be able to read
this and say what happened and what to do next.

---

## 0. THE OPERATOR DIRECTIVE — READ THIS BEFORE ANYTHING ELSE

**2026-09-24, valid to 2026-10-01. Three lanes, everything else frozen.
THIS SESSION IS LANE 2, the agent.**

Lane 2 is: lift the gag (with rules-4 from lane 1), the Monday weekly
report with PDF, reply-engine drafts visible in `#replies-productive`, and
"what are we working on" / "what is happening with <domain>" answering
**from what exists**.

**FROZEN IN LANE 2:** the portal, the OSS survey beyond the automated
Friday run, internal-mode extras, Phase D item 4 until the ledger
write-back exists, and **latency below what is measured now**.

Handoff thresholds changed the same day: write one at 600k tokens and keep
working, write a fresh one at 850k and stop for `/clear`. Never mid-push,
never mid-incident.

### 0a. THE LATENCY WORK IS FROZEN AND PARKED, NOT LOST

Branch **`slack-agent-latency-parked`** at **`3c5c0528`**, pushed. It was
half-built when the directive landed and is committed there rather than on
`slack-agent`, because `answer_model` is wired into `_respond` and merging
it would ship frozen work.

**IT IS WIRED AND UNMEASURED.** Sonnet for client answer composition, a
two-to-four-sentence client length rule, and a `reasoning_heavy` escape
(relay / four-or-more tools / explanation) that keeps the stronger model.
**No replay has been run against it**, so there is no evidence it holds
quality — which was the operator's own condition for keeping it. Do not
merge it on the strength of it looking right.

Two things in it worth separating when it thaws:

- **THE CATALOGUE MARKS NOTHING "REASONING-HEAVY".** The instruction
  assumed a marking that does not exist. The parked branch DEFINES one
  from the corpus. That definition is the part to argue with first.
- **`seconds_planning` / `seconds_answering`** is instrumentation, not a
  latency change. It turns "~21s is answer composition" from a subtraction
  into a measurement, and it is the piece worth rescuing independently of
  whatever happens to the rest.

Streaming / edit-in-place was never started and is blocked regardless:
`src/providers/slack.py` has `POST_MESSAGE = "/chat.postMessage"` and no
`chat.update`, and `src/providers/*` is forbidden to this branch. It is
production's, exactly like the file-upload route.

**Branch `slack-agent` at `9175243c`, pushed and verified.** It merges
master at `522495b3`; master has since moved to at least `d6a719c2` —
fetch and check before writing anything.

---

## 1. THE HEADLINE, AND IT IS NOT THE LATENCY

**THE BRANCH WAS NEVER GREEN, AND THE LAST HANDOFF DID NOT SAY SO.**

    full suite, pre-merge tip 20586a63      136 failures
    full suite, this branch 041a1fbb         82 failures

Nothing in the morning handoff is untrue about it; it simply never ran the
whole suite, and "hygiene 13 of 13, the slack modules green" reads exactly
like a green suite to the next reader. It was read that way here for most
of a session.

**Compare these as SETS BY NAME, never as counts.** Against the 136:
**4 introduced, 58 fixed.** Three of the four are MASTER'S — verified
against master alone at `d6a719c2` — where `heyreach.stop_lead` is enabled
by one commit and asserted unsupported by two tests, plus a linkedin
field-name test. The fourth is §1a.

Of the 58: 31 are the gag/ticket flow (§4a), ten are
`test_what_are_we_working_on`, and the rest follow from the merge.

### 1a. ONE INTERMITTENT, DIAGNOSED AND STILL OPEN

    FAIL test_a_checkpoint_costs_what_it_changed
         .ConcurrencyGlmFound.test_concurrent_appends_do_not_lose_entries
    AssertionError: append raised under contention:
        [PermissionError(13, 'Permission denied')]

`qj.append` from four threads, 25 appends each. **Not caused by anything on
this branch** — no code here touches the queue journal — and it appears in
neither the 136 baseline nor the 123 run, so it is a first sighting rather
than a regression this merge carries.

NOT DISMISSED, and not solved either. Tried: five runs of the module alone
(clean), and eight concurrent copies of it in two rounds (clean). It did
not reproduce. `PermissionError(13)` on Windows is what a file-replace
hits when something else holds the handle for an instant, so the suspect
is the journal's own lock/replace path under load rather than the test.

**What is still owed on it:** an isolated full-suite run, which is the
third of the three diagnoses `CLAUDE.md` requires and the one not done
here. Until then it is an open intermittent on a WRITE path, which is the
kind that matters.

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

## 4. THE GAG, AND WHAT PRODUCTION STILL OWES

### 4a. A CLIENT CHANGE REQUEST REACHED NOBODY — FIXED, AND IT IS A LOOSENING

`CLIENT_CHANNEL_GAG` returned before section 2a of `_respond`, and
`_raise_ticket` is below it. So a client asking us to CHANGE something
produced a `kind: gagged` row, one line on the loop's stdout, and nothing
else: no ticket, no internal post, nobody told. The question catalogue's
highest-severity shape in the whole corpus is a client change request. It
was also 31 of the 123 failures.

**OPERATOR DECISION 2026-09-24: fixed on this branch.** The gag moved to
sit AFTER the change-request intake. All 31 pass.

**SAY THE LOOSENING OUT LOUD.** The agent posts to a client channel again,
for change requests only. The argument: the gag's three faults were all in
the MODEL-ANSWERED path — a provider flag read as a classification, the
model reaching for the fallback, sixteen serial round trips — and nothing
above the new line calls a model or reads a provider. `_open_request` and
`_raise_ticket` are template text out of `slackrequests`, and
`restate(client_facing=...)` already has its own guards
(`..._names_nobody_at_resonate`, `..._promises_a_time`).

One client path stays behind the gag: accepting the first-send offer,
because registering a follow-up promises a later message AND reads the
provider.

**TO PUT THE SILENCE BACK:** move the 2d block to the top of `_respond`,
where it was the first statement after `scope`. The 31 go red with it. It
is written at the block, and
`tests/test_the_gag_stops_the_answer_not_the_request.py` pins both halves
so the size of the hole is visible rather than inferred.

Writing that test caught two things worth keeping: a `ROWS` shape
`slackscope.resolve` does not understand does not raise — the channel
resolves UNBOUND and an unbound turn is never gagged, so four assertions
passed against a scope the test was not about; and the test wrote **two
real tickets into `docs/requests/`**, because `isolate()` moves the store
and the ticket directory has its own `SLACK_REQUESTS_DIR`. `slackrequests`
carries a comment saying that happened once before and the files were
deleted by hand. It says so at the constant that fixes it, and it still did
not prevent the second occurrence. **A guard asserting `docs/requests/` is
empty after the suite is the thing that would**, and it is not built.

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

## 7. THE LIVE REPLAY IS DONE — `docs/AGENT-REPLAY-2026-09-24.md`

**THE TARGET IS NOT MET.** Client scope, 11 of 33 real questions, live
provider, live model, `--lift-gag`, nothing posted:

    client p50   25.4s     target 15s
    client p95   37.8s     target 30s

The comparison is NOT 24.3s → 26.6s: the published baseline p50 included
eleven gagged 0.0s answers. Over the 21 it answered the baseline median was
≈108s. So: turns over 82s **11 of 21 → 0 of 33**, p95 **132.3s → 37.8s**,
five-tool turn **108.3s → 35.7s**.

**AND THE BOTTLENECK MOVED. "100% of the latency is serial provider HTTP"
IS NOW FALSE** — it was true when written. A 0-tool turn costs 4.4s, a
1-tool broad-route turn costs 26.2s, and the A/B says `working_on` is 5.4s
of it, so **~21s of every turn is answer composition**: one model call,
untouched by this increment and immune to caching or parallelism. The next
latency increment is about the model — a smaller one for short answers,
streaming, or a shorter answer prompt. Measure first; that rule has paid
three times on this branch now.

### 7a. And the route that was supposed to fix the length failures

`length` is 6 of 33, and **five of the six TOOK the broad route and still
answered long**. The plan was the cause of the volume and is not the whole
cause of the length. That is now a prompt problem, separable from the plan,
which it was not before.

### 7b. What the run cost to get right

Three live runs. The first resolved **zero client scopes** because the copy
list said `workspaces.json` and the file is `workspaces.jsonl` — so it
measured the scope the target is not stated in. The second measured
pre-fix code and was killed at 6 of 33.

`scratchpad/replay_after.sh` carries the setup; `--lift-gag` is on the
harness and is safe structurally, not by promise: the script has no write
path to Slack, because `respond` returns a dict and the loop is not
imported there.

### 7c. THE ROUTE SHIPPED INERT, AND EIGHTEEN TESTS SAID OTHERWISE

The broad-question route fired **zero times** on the first replay. Every
real question arrives as `<@U0C3CBAP6BB> what is running`, and the guard
that rejects "what's new with 491" matches a bare `@` — so it rejected the
whole corpus. `requests.strip_mentions` already existed and three other
modules already called it. **The fixture was the defect.** Fixed at
`21222253`; the tests now use phrasings copied verbatim out of
`work/slack-agent.jsonl`, mentions and all, and the route fires 8 of 33.

This is the argument for the replay over the suite, in one example.

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

## 9. WHAT TO DO NEXT, IN ORDER — LANE 2 ONLY

**§0 outranks this list.** Anything below that is not lane 2 is frozen
until 2026-10-01 and stays here for October.

1. **Tell production to start `weekly-report`.** §10. Monday is 2026-09-28
   and nothing has started the loop, so as things stand there is no report.
2. `working_on` and `account_status` answering FROM WHAT EXISTS — the
   tools exist (§5); the question is what they do while the ledger
   write-back does not.
3. Reply-engine drafts visible in `#replies-productive`.
4. Lifting the gag, which waits on rules-4 from lane 1. **Note it is
   already PARTLY lifted**: change requests reach the operator again as of
   `fcced109`; answers are still gagged. §4a.

FROZEN, AND HERE FOR OCTOBER: the missed-mention sweep (§6's two
constraints still apply when it thaws), item 5's 10-vs-7 window decision
(§5), and the whole latency increment (§0a).
5. **Tell production the gag was loosened.** §4a. It is done, not pending,
   and it changes when a safety mechanism they set returns. The revert is
   one block move.
6. The `length` failures are now a PROMPT problem, not a plan problem. §7a -
   five of six took the broad route and still answered long.
7. A guard that `docs/requests/` is empty after the suite. §4a - the same
   accident has now happened twice.

---

## 10. THE MONDAY REPORT — DRY RUN DONE, ONE THING PRODUCTION MUST DO

Walked Monday 2026-09-28 end to end against a copy of production's `work/`,
clock pinned as an absolute instant rather than derived from the zone under
test. Committed at `9175243c`.

**THE DECISION MACHINERY IS SOUND and was not touched.** Preview 07:30 →
window open 07:45 → delivered 08:00 → `already_done` 08:05; a stop holds;
an anonymous stop is refused; a tick that first runs after 08:00 refuses to
post, because nobody had the window in which to stop it. 28 existing tests
in `test_the_monday_report_can_be_stopped.py` already cover it.

**PRODUCTION MUST START THE LOOP.** It was in no supervision table at all —
not started on boot, not restarted, never reported by `--status`. It is in
`start_monitors.MONITORS` now as `weekly-report` at a 300s interval, and
`--status` currently says `weekly-report NEVER`. **Nothing has started it,
so as things stand Monday produces no report.** Lane 3 cuts over that same
night after 23:00 Zagreb, so it needs starting on the old host for Monday
morning and confirming on the new one afterwards.

That is the THIRD time this gap has been closed here. `digest_loop` and
`slack_followup_loop` were both found not running for the same reason, and
both comments sit two lines above the new entry.

### 10a. Two defects the dry run found

- **The PDF cover was dated by the BUILD, not by its Monday.** The filename
  used `monday`; the cover used `report["read_at"]`. On a punctual Monday
  they agree and nothing shows; on a retried or late one the client gets a
  document naming the wrong week. Fixed, and it now carries `report_id`
  too, because a person attaches this by hand.
- **Nothing checked the client document against the client backstop.** It
  is the one artefact here that reaches a client unmediated. It passes.
  The test has a control beside it, because the obvious way to write that
  check is already on the lesson list: `assertNotIn(b"...")` against a
  Flate-compressed PDF passes on the compression rather than the absence.
  The helper inflates the streams and reads the text operators.

### 10b. The ledger gap degrades correctly, and stays production's

The report says **"1,522 account(s) cannot be placed ... This is NOT a
count of untouched accounts and must not be read as one."** That is the
write-back blocker showing up honestly. Per the directive it is lane 1's
and frozen beyond what the status post needs — do not build around it.

### 10c. Still production's

`src/providers/slack.py` has no file-upload route, so the PDF is written to
`work/reports/` and a person attaches it. The preview text says so out loud
rather than leaving it to be discovered on a Monday.
