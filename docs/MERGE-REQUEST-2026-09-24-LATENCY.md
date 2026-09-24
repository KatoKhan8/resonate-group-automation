# Merge request — the latency increment, and three things found on the way

Branch `slack-agent`. Two commits: the master merge, and this increment.
Nothing pushed to master, nothing written to `work/`, no provider write.

---

## 0. THE SUITE, AND A CLAIM THIS DOCUMENT NEARLY MADE

**The branch was never green.** The full suite at the pre-merge tip
`20586a63` is **136 failures**. Nothing in the last handoff says so, and
"hygiene 17/17, the slack modules green" reads exactly like it does.

| run | failures |
|---|---:|
| branch tip `20586a63`, before any of this | **136** |
| this branch, first attempt | 154 |
| this branch, after the cache was scoped | **123** |

Diffed as SETS BY NAME, not compared as counts: **3 introduced, 16 fixed**.
All three introduced are MASTER'S, verified against master alone at
`d6a719c2` - `heyreach.stop_lead` is enabled by one master commit and
asserted unsupported by two master tests, plus a linkedin field-name test.
They arrived with the merge and are not this branch's to fix.

Ten of the sixteen fixed are `test_what_are_we_working_on`.

### 0a. AND THE FIRST ATTEMPT WAS REPORTED AS VERIFIED WHEN IT WAS NOT

The cache was first built process-global, and it cost **154 failures** -
thirty of them its own. Every targeted module run passed before it was
committed, because each module is green alone and red after its neighbour.
**Not one of the 154 named the cache.** They said

    AssertionError: 'unreadable' != 40

in a module about scheduling horizons, three layers from the cause.

The signal used to watch the running suite was worse than useless:
`grep -c '^FAIL:'` against a live log, when unittest prints those blocks
only in the END-OF-RUN summary. It returned 0 for thirty minutes and could
not have returned anything else. **Absence of a signal was read as a green
signal.**

Fixed by scoping rather than flagging - `readback.turn()`, opened by
`respond` - which gives up nothing measured, because every repeat the cache
removes is inside one turn. Ninth for the lesson list, and the first one on
it that is about how the checking was done rather than what the check said.

---

## 1. WHAT WAS ASKED, AND WHAT IT MEASURES AT

The operator's sequencing: **latency before the gag lifts.** A 60-second
readback cache keyed by campaign and route, independent reads in parallel,
and fewer tools planned per broad question. Target p50 under 15s and p95
under 30s in client scope.

### 1a. The A/B, and why you can trust the "before"

`scratchpad/measure_fanout.py` runs the four campaign-walking tools against
a stub provider at a fixed per-call cost. **The "before" configuration is
not a revert — it is `PROVIDER_FANOUT = 1` and `READBACK_TTL = 0`**, which
is exactly the old code path, so both halves run against the same tree.

Calibrated at **1.36s per call**, which is what the 2026-09-23 replay
measured (`sends_today` 21.72s over 8 campaigns = 16 round trips):

| tool | before | after | provider calls |
|---|---:|---:|---|
| `sends_today` | 21.78s | **5.44s** | 16 → 16 |
| `activity_this_week` | 40.82s | **2.72s** | 30 → 4 |
| `weekly_plan` | 81.64s | **6.81s** | 60 → 30 |
| `lead_counts` | 54.42s | **2.72s** | 40 → 10 |
| **a four-tool turn** | **198.65s** | **17.69s** | **146 → 60** |

**11.2× faster, and 86 of 146 provider calls never happen.**

### 1a-ii. And the commonest question does not make that turn at all

The four-tool table is the worst case. The shape people actually ask —
"what is running", "what are you working on" — used to plan five tools and
now plans one, so the number that matters for it is `working_on` end to
end, measured the same way:

| | before | after |
|---|---:|---:|
| `working_on`, one call | 43.57s | **5.44s** |
| provider calls | 32 | **16** |

**A broad question in client scope: a five-tool turn, replaced by one call
at 5.44s.** That is the shape behind all six length failures in the replay
and eleven of the twenty-one answered questions that used the full budget.

The reason to believe the model: the BEFORE column reproduces the live
replay almost exactly without being fitted to it — `sends_today` 21.78s
here against **21.72s measured live**, `activity_this_week` 40.82s against
**44.81s**. The stub was calibrated on one number and predicted the others.

### 1b. AND IT IS NOT THE LIVE NUMBER, WHICH IS THE POINT

**This is a mechanism measurement, not a latency measurement.** It proves
the serial round trips are gone. It cannot prove p50 or p95, because the
provider is a stub and a stub has no tail — no slow campaign, no retry, no
491 with 645 queue rows. The live p50/p95 has to come from the replay
harness against the real provider, and **that run is not in this merge
request.** Anyone reading 17.69s as "p95 is now 18s" is reading it wrong.

What the arithmetic does support: the answered half of the 2026-09-23
replay was 100% serial provider HTTP, and roughly 60% of the calls behind
it are now gone with the rest running six at a time. p95 132.3s has a long
way to fall before 30s is in doubt.

### 1c. THE TARGET IS IN CLIENT SCOPE, AND CLIENT SCOPE ANSWERS IN 0.0s

Worth stating plainly, because it is circular and the circle is easy to
walk into. The target is **p50 under 15s and p95 under 30s in client
scope.** `CLIENT_CHANNEL_GAG` returns before anything is planned, so every
client question today costs 0.0 seconds and produces nothing. A live replay
measures the gag, not the latency — the 2026-09-23 run's 11 of 32 at
`how: gagged` is exactly that.

And the gag is not to be lifted until the latency is fixed. So the latency
in the scope that matters cannot be measured in the state that precedes
lifting it.

**The replay is the way out, because it posts nothing.** Lifting the gag
inside the replay process is not lifting it in production: no Slack write
exists on that path, and provider reads are the only live thing about it.
The harness needs a flag for that, and it is the next thing on this branch
rather than something already in this merge request. Until then, every
latency number here — live or stub — is about the internal half.

---

## 2. WHAT IS IN IT

### 2a. The 60-second readback cache — `src/slackagentreadback.py`

Keyed on `(route, campaign_id)`, per-process, never persisted, errors never
cached. Two properties are tested harder than the saving:

1. **A reused value keeps the time it was ACTUALLY fetched.** `read_at` is
   what every downstream answer stamps itself with, so a reused value
   wearing a fresh timestamp is the one way this turns a correct system
   into a confidently wrong one. `read_age_seconds` carries how old.
2. **A failure is not cached.** One transient outage held for a minute is
   sixty seconds of invented outage, and nothing is written on the raising
   path, so the previous good value survives rather than being evicted.

Concurrent reads of the same key **coalesce**, because the cache is cold
exactly when the fan-out goes wide — without that it saves nothing on the
first turn after a restart, which is the turn that needs it most.

### 2b. Bounded parallel per-campaign reads — `src/slackagenttools.py`

`_fan_out(ids, read)` returns `[(id, value, exception_or_None)]` **in the
caller's order**. Order matters and is tested: `_campaigns_to_read` hands
over newest-first and capped answers walk that list, so completion order
would silently change which campaigns an answer is about. The exception is
handed back rather than raised or swallowed, because the five loops it
replaces each treat an unreadable campaign differently.

Applied to `sends_today`, `activity_this_week`, `weekly_plan`,
`lead_counts` and `_forward_window`. **Reads are parallel; accumulation
stays serial on one thread** — a running total summed from a pool is a race
whose symptom is a number that is only slightly wrong.

`PROVIDER_FANOUT = 6`. **It bounds the burst, not the rate.** Nothing here
spends a per-minute budget against the provider's documented 60 calls a
minute, and there is a test that demonstrates that rather than asserting it
of a comment.

### 2c. A broad question plans ONE tool — `src/slackconversation.py`

All six length failures in the replay were one shape — "what is running",
"what are you working on", "what can we do now" — answered in 9–11
sentences against a prompt asking for two to six. The cause was never the
prompt: five tools make a large material and the model summarises what it
is handed. `working_on` answers exactly those in one call.

The route is taken **before the planner model is asked**, which removes a
second round trip: a question with exactly one right plan does not need a
model call to discover it. Scope still decides — `working_on` is checked
against that channel's catalogue, not assumed.

**The negative cases are the load-bearing half**, because a false positive
answers a specific question with a summary, which is worse than the fan-out
it replaces. The matcher must match end to end and refuses anything naming
a campaign id, a domain or an `@`, so "what's new with 491" still fans out.

It also fixes §2e of the last handoff by accident: the keyword fallback for
"running" is `monitors`, so **"what is running" was the question that got
answered with monitor health.** It now routes to `working_on`.

### 2d. The replay harness — `scripts/slack_agent_replay.py`

**`--catalogue` parsed the wrong shape and scored zero questions.** It
matched `- "quoted line"`; the catalogue has only ever used blockquotes in
emphasis. It now parses 27 phrasings, joins the one that runs onto a second
line, and keeps back-to-back ones separate. **And it now exits non-zero
when it parses none**, because a corpus flag that silently adds nothing
looks exactly like a corpus with nothing in it.

**A seventh check, `subject`: does the answer name the thing the question
asked about?** `numbers` reads the turn's own guard, which fires on a
figure ABSENT from the material and cannot fire on a figure that is
present, correct, and answers a different question. The first row of the
2026-09-23 replay is exactly that and scored clean on all six.

`n/a` where no subject is extractable, never `pass` — the last audit's
`terms` column was 32 `n/a` and got read as 32 passes once already.

---

## 3. THREE THINGS FOUND ON THE WAY, AND ONE MATTERS MORE THAN THIS MERGE

### 3a. A CLIENT CHANGE REQUEST NOW REACHES NOBODY

**This is the one to read.** `CLIENT_CHANNEL_GAG` returns at
`slackconversation.py:1406`. `_raise_ticket` is at **1454**. So in a client
channel the turn returns before the ticket is written, and the loop's
handling of a gagged turn (`scripts/slack_agent_loop.py:254`) writes a
`kind: gagged` row to `work/slack-agent.jsonl`, emits a line to stdout, and
returns. **No Slack post, no ticket, no internal notification.**

The question catalogue names the highest-severity shape in the whole corpus
as a client change request — a reply-stop complaint with four question
marks. Today that produces a log line and nothing else. The gag was set to
stop the agent saying something wrong to a client; it also stopped the
operator finding out the client asked.

It is also **31 tests red on this branch before this merge** — verified
identical by name before and after, diffed as sets rather than compared as
counts — across `test_slack`, `test_slack_knowledge` and
`test_slack_request_tickets`, 12 of them naming `gagged` directly.

**This is production's decision, not this branch's**, and it is a third
outstanding item on the gag alongside the two the last handoff named. The
cheapest fix is to let the ticket path run before the gag returns: a ticket
is an internal write, not client-visible text.

### 3b. A third provider read path that was in nobody's budget

`_forward_window` called `bison.sending_schedule` directly — three days by
ten campaigns, **thirty serial live HTTPS requests**, bypassing
`slackagentreadback` entirely. The readback module's docstring said two
functions reach the provider and they are "the ONLY provider calls here";
that was true of the file and false of the agent. Neither the cache nor the
fan-out covered it, for the same reason: it was not there to be found.

Found by stubbing the campaign and queue reads and profiling `weekly_plan`
anyway — it still cost 3.4 seconds and still went to the network. **The
lesson list's method again: nothing complained.** It is routed through
`readback.sending_schedule` now and is 81.64s → 6.81s of the table above.

### 3c. The hygiene guard collected 13 of 17 when run directly

Master's new `TestTheExemptionStaysNarrow` landed BELOW
`if __name__ == "__main__": unittest.main()`, so running the file directly
called `main()` before the class existed — the four tests guarding the
exemption's own size silently among the missing, under a clean
`Ran 13 tests`. `-m unittest` imports first and ran all 17, so it was green
both ways and wrong in one. The block is at the end of the file now.

**Eighth for the list**, and the same shape as the other seven.

And a fourth, smaller: `test_a_whole_turn_in_a_client_channel_discards_a_leaking_answer`
— the only end-to-end proof of the scope backstop — has been erroring with
a `TypeError` since the gag was set, because it asserts against a `reply`
that is now `None`. It went red in a way that reads as a broken test rather
than a missing guarantee. It now lifts the gag for its own duration, and
the gag has its own test beside it, so **the day the gag lifts is not the
day that proof starts running.**

---

## 4. THE MERGE ITSELF

Master moved ten commits. Two conflicts, both real; the substantive one is
`tests/test_fixture_hygiene.py`, where master and this branch reached the
same two-file exemption independently under different names.

The merge keeps master's `HYGIENE_EXEMPT` tuple and this branch's
`--others --exclude-standard` walk. **It does not keep master's
`tracked_files` filter**, which dropped the two exempt files from the
corpus outright — wider than the exemption that was argued for, since it
also stopped them being checked for phone numbers, client domains and live
account figures. The exemption was granted for a name, a handle and an
address; those three checks skip the files, and the corpus still carries
them.

---

## 5. WHAT IS STILL OWED

- **The live replay run.** §1b. The number the operator asked for is the
  live p50/p95, and this merge request has the mechanism number instead.
- `PROVIDER_FANOUT` bounds the burst and not the rate. If turn volume ever
  rises, that needs a shared token bucket.
- `scripts/suite_verdict.txt` is TRACKED and is written by
  `scripts/run_suite.py` in whichever checkout runs it. The copy in git is
  from production's checkout on another day, and reading it as this
  branch's verdict is a mistake this session made once before catching it.

## 6. VERIFIED BLOCKED, CHECKED RATHER THAN ASSUMED

Both of the operator's item-4 blockers still stand on master:

- **`rules-4`** — `replies.VERSION` is `"rules-3"` and no `RULE_HASH`,
  `RULES_HASH` or `RULE_FINGERPRINT` is defined anywhere in `src/`. So
  `replyverdict.positive_confirmed` is 0 and Phase D item 4 correctly posts
  nothing.
- **The ledger write-back** — production's own `work/queue.jsonl` carries
  **one** confirming event across **1,543 records**: a single `push_marked`,
  and zero `email_delivered` or `linkedin_connected`. `_ledger_carries_sends`
  needs `touches >= provider_sent // 10`, so one touch cannot clear any
  threshold above ten sends. It is `False`, `account_status` degrades
  honestly, and this needed no provider call to establish.

Neither moved with master's ten commits.
