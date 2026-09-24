# Slack agent — handoff, 2026-09-24 morning

Supersedes `SLACK-AGENT-HANDOFF-2026-09-23-FINAL.md` and every earlier one.
Written to the test `CLAUDE.md` sets: a fresh session on another machine,
with a clone and the secrets supplied separately, should be able to read
this and say what happened and what to do next.

**Branch `slack-agent` at `fe801cfa`, pushed and verified.** It merges
master at `9b04873a`. **Master moved seven times on 2026-09-23** — fetch
and check before writing anything.

---

## 1. WHAT THE OVERNIGHT QUEUE FOUND

Three of the seven items are done. **The measurements are the deliverable**;
the code changes are smaller than what was learned.

| item | state |
|---|---|
| 1. replay audit | **DONE** — `docs/AGENT-REPLAY-2026-09-23.md` |
| 2. latency | **specified from data, NOT started** — §5 |
| 3. missed mentions / deliverables | **not started** — §5 |
| 4. Monday dry run | **not started** — §5 |
| 5. meetings, promises, account status | **not started** — §5 |
| 6. adversarial sweep | **DONE** — 921 probes, one leak fixed |
| 7. improvement plan | **DONE** — `docs/AGENT-IMPROVEMENT-PLAN.md` |

---

## 2. THE REPLAY SCORECARD — `docs/AGENT-REPLAY-2026-09-23.md`

32 real questions since 2026-09-21, replayed through their **original
channel and user**, live provider reads, live `claude-opus-5`, nothing
posted.

### 2a. A THIRD OF REAL TRAFFIC GETS NO ANSWER

**11 of 32 — every one from a client — returned nothing.** `how: gagged`,
0.0 seconds. Among them:

    which three campaigns are awaiting my approval?
    what's waiting on my approval?
    what went out this week?
    what are the results so far?
    Bruno pita jesmo li provukli struju...

`CLIENT_CHANNEL_GAG` is correct and was set for three real faults. But the
number it forces into view is that **34% of real traffic is client traffic
and the agent answers none of it.**

**And it means the audit cannot score the client half at all.** The `terms`
column is `n/a` 32 times out of 32 — not because nothing leaked, but
because **no client answer exists to check**. Any claim that client scoping
is healthy rests on §4's 921-probe sweep, not on this replay. A column of
`n/a` must not be read as a column of passes.

### 2b. LATENCY IS FOUR TIMES THE TARGET

    p50   24.3s        target: client turns under 30s
    p95  132.3s
    max  176.0s

Almost perfectly linear in tool calls — 0 tools **4.5s**, 1 tool 13.3s, 5
tools **108.3s** median. Eleven of the twenty-one answered questions used
the full five-call budget and every one took over 82 seconds.

**The cause, measured per tool:**

    knowledge pack        0.00s
    batch_state           0.00s     local
    next_actions          0.00s     local
    sends_today          21.72s     provider
    activity_this_week   44.81s     provider

**100% of the latency is serial provider HTTP.** `sends_today` reads up to
8 campaigns, each a `campaign` GET plus a `scheduled_emails` GET;
`activity_this_week` reads ten. Sixteen to twenty sequential round trips.

**THE KNOWLEDGE PACK IS ALREADY FREE.** "Prebuilt pack after every restart"
was one of the three fixes proposed for this. It would save **zero
seconds** — cached it is 0.00s in a turn and 0.13s to rebuild cold. It is
named here so it is not proposed again; finding that out cost one timing
run and saved an increment.

### 2c. THE SIX LENGTH FAILURES ARE ONE CAUSE

Every one is the same question shape — "what is running", "what are you
working on", "what can we do now" — answered in **9–11 sentences and
1,036–1,594 characters** against a prompt asking for two to six.

The cause is not the prompt. **A broad question plans five tools, five
readbacks make a large material, and the model summarises all of it.** The
length rule loses to the volume of material, so the fix belongs at the PLAN.

`working_on` (shipped 2026-09-23) answers exactly those questions in **one
call**, which makes this an answer-quality fix that is probably also the
second-largest latency win.

### 2d. THE SCORES

| check | pass | fail | n/a |
|---|---|---|---|
| numbers | 31 | 1 | 0 |
| scope | 32 | 0 | 0 |
| terms | 0 | 0 | **32** |
| promise | 21 | 0 | 11 |
| language | 21 | 0 | 11 |
| length | 15 | **6** | 11 |

"Clean: 25 of 32" is the flattering reading. **Of the 21 answers that
actually exist, 14 were fully clean — 67%.**

The single `numbers` failure is the guard WORKING: the model produced a
figure of `73` absent from the material and the turn **replaced the
answer**.

### 2e. WHAT THE AUDIT COULD NOT SEE, AND IT MATTERS

1. **Client quality, at all** — §2a.
2. **The catalogue corpus scored zero questions.** `--catalogue` parses
   `- "quoted line"` and `SLACK-AGENT-QUESTION-CATALOGUE.md` does not use
   that shape. **A defect in the harness, not an absence of questions.**
3. **Semantic correctness.** `numbers` reads the turn's own `guard`, so it
   catches a figure ABSENT from the material and **cannot** catch the right
   number answering the wrong question. The first question in the log —
   `what is running` — was answered with **monitor health**, and scores
   clean on every check written.

---

## 3. THE IMPROVEMENT PLAN — `docs/AGENT-IMPROVEMENT-PLAN.md`

Ten items ranked by measured impact. **Two sequencing notes matter more
than the ranking itself:**

### 3a. The gag is first on size and must NOT be lifted first

11 of 32 unanswered is the largest number in the audit. But one of the
three faults that caused the gag was **a seven-minute turn**, and p95 is
132s. **Lifting the gag onto a 132-second turn recreates one of the faults
that caused it.** So: items 2 and 3 of the plan (cache, parallelism) are
the precondition, and a ranking by impact alone would have got this wrong.

Of the three original faults, two now have mechanisms: the false positives
are held by `replyverdict.positive_confirmed` (0 until a verdict can be
proved current), and the latency is addressed by the plan's items 2–3. The
third — "awaiting your approval" for an operator decision — **still needs
its own check.**

### 3b. An answer-quality fix is probably the second-biggest latency win

Plan item 4 (route broad questions to `working_on` instead of fanning out
to five tools) fixes §2c's six length failures at the cause **and removes
four provider-touching calls from the most common question shape**. It
compounds with the cache rather than competing with it.

---

## 4. THE ADVERSARIAL SWEEP, AND A GUARD THAT AUDITED EVERYTHING BUT ITSELF

`tests/test_the_client_scope_under_attack.py` — **921 probes**, offline, no
model, no provider: 37 crafted arguments × 24 client tools, plus 25
sentences and 8 instruction overrides.

**It found a leak on its first run:**

    "Claude is reviewing the branch."   reached a client channel

`INTERNAL_WORKER_TERMS` held `"claude code"` and not bare `"claude"`, while
`qwen`, `glm` and `grok` were all there. Fixed. The trade-off is written
where the term is: `Claude` is also a French given name, so such an answer
now gets the fallback — the safe direction.

**Five of the 25 sentences must NOT be refused**, and that is the control: a
backstop that refused everything would pass all twenty leak assertions and
leave the agent useless.

### 4a. The PII guard could not see a file until it was committed

Found by it catching me. I wrote the final handoff — **a section of which
describes the guard catching a real name in a handoff** — ran
`test_fixture_hygiene`, was told 13 of 13, and committed a real handle.

`tracked_files()` called `git ls-files`, which lists **only what is already
tracked**. A brand-new file is invisible until staged. So the green
described the *previous* state of the repository, and write → check →
commit is exactly the order in which that check could not fail.

Fixed with `--others --exclude-standard`, and **proven**: with the guard
green, an untracked file naming a real person was dropped into `docs/`, the
names assertion went red and named it, and removing it returned green.

**`tests/test_fixture_hygiene` is 13 of 13**, from 10 at the start of
2026-09-23.

---

## 5. ITEMS 2–5, SPECIFIED FROM DATA

**Item 2 — latency.** Target: client turns under 30s. Current p95 132s.
Build, in this order:

1. **A 60-second readback cache keyed on campaign id**, in
   `src/slackagentreadback.py`. A five-call turn reads the same campaign up
   to four times. Per-process, never persisted, and every cached readback
   keeps the time it was ACTUALLY fetched so a stale value is visible.
2. **Parallel per-campaign reads** in `sends_today`, `activity_this_week`,
   `weekly_plan`, `lead_counts`. Bounded concurrency; the provider's
   documented limit is 60 calls/min.
3. **Do not prebuild the knowledge pack.** §2b.

**Item 3 — missed mentions and deliverables.** Measure before building: the
replay found no missed mention and **could not**, because it reads
questions the agent already logged. Sweep `#resonate-os` history against
`work/slack-agent.jsonl` for mentions with no `answered` row, and report the
count first. Deliverables ranked last in the plan on measured demand — 1 of
32 real questions asked for one.

**Item 4 — Monday dry run.** `weeklyreportwatch` + `weeklyreportpdf` exist
and are tested; the loop has **never been started** and there is no
`work/heartbeat/weekly-report.json`. The dry run needs production's `work/`
and the first real Monday is 2026-09-28.

**Item 5 — meetings command, promise scan, account status.** The meetings
command and promise scan are S-sized and self-contained. **Account status
from the ledger is BLOCKED and verified so**: `_ledger_carries_sends` is
`False` against production's own `work/`, `account_status` already degrades
honestly, and 49 existing tests cover that degradation.

---

## 6. WHAT PRODUCTION OWES, AND WHO OWNS THE CACHE

**Production's, and nothing on this branch can do them:**

1. **The gag decision.** Whether to lift it, and the "awaiting your
   approval" check that is its third outstanding fault. §3a.
2. **The ledger write-back.** `_ledger_carries_sends` is `False`; until it
   is true, `account_status` cannot answer and `unanswerable` stays
   non-zero in every client-facing account figure.
3. **`rules-4` and a rule HASH.** `replies.VERSION` is still `"rules-3"`
   and no `RULE_HASH` / `RULES_HASH` / `RULE_FINGERPRINT` exists in `src/`.
   Until one does, `replyverdict.positive_confirmed` is 0 and Phase D item
   4 correctly posts nothing.
4. **Supervise the briefing loop.** It is not in
   `scripts/start_monitors.py`'s `MONITORS` table, so it is not restarted
   on reboot and `--status` never reports it.
5. **Start the Monday report loop.** No heartbeat exists; first fire would
   be 2026-09-28.
6. **A Slack file-upload route.** `src/providers/slack.py` has `post()` and
   nothing else, so the weekly PDF is written to `work/reports/` and a
   person attaches it. `src/providers/*` is forbidden to this branch.
7. **`src/replies.py`'s live path.** This branch has stepped around the
   `rules-4` work four times on purpose.

**THE READBACK CACHE IS THIS BRANCH'S, NOT PRODUCTION'S.** It belongs in
`src/slackagentreadback.py`, which is the agent's own reader and is not on
the forbidden list — `src/providers/*` is, and the cache does not need to
go there. Same for the parallelism: the per-campaign loops live in
`slackagenttools`. **Neither is blocked on production.** They are the next
increment and the only reason they are not done is that this session ran
out of room, not out of permission.

---

## 7. THE RULES, VERIFIED

Never merges or pushes to master — **verified, master untouched**. Never
edits `config/.env`, `work/`, `src/providers/*` or
`scripts/*_watch_loop.py`. Production's `work/` was **read** and never
written: the replay ran against copies in the session scratchpad with
`WORKSPACES` and `SLACK_THREADS` pointed there, so thread memory from 32
replayed turns never touched the live file. A merge request per increment,
delivered as a doc plus one line in `#resonate-os`. Adversarial probes
offline only — the 921-probe sweep has no model, no provider and no
network.

---

## 8. THE LESSON, NOW AT SEVEN

**A test can be green because it is unfalsifiable, and that looks exactly
like a test that passes.**

    assertNotIn(b"...") against a Flate-compressed PDF
    schedule tests building `now` from the zone they were pinning
    a version guard that catches a BUMP but not the DRIFT
    an internal-tool enumeration derived from the registry it polices
    an override test whose sentence never opened with a compose verb
    "it is a count" with no control proving it is ever a list
    a PII guard that could not see a file until it was committed

None was found by writing more tests. All seven came from **breaking the
code deliberately and being unsatisfied with how little complained.**

### 8a. And the corollary, which paid again last night

**Check the premise before building to it.** "Prebuild the knowledge pack"
was a reasonable-sounding latency fix, and the pack costs **0.00 seconds**.
One timing run replaced an increment of work with a line in a document.
