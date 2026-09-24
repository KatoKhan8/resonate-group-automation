# Agent replay audit — 2026-09-23

Every real question asked of the Slack agent since 2026-09-21, replayed
through its **original channel and user**, scored on the operator's six
criteria. Provider reads live, model live (`claude-opus-5`), nothing posted.

    scripts/slack_agent_replay.py --since 2026-09-21 --catalogue

**32 questions. 21 answered. 11 got nothing at all.**

---

## 1. THE HEADLINE, AND IT IS NOT A QUALITY PROBLEM

**Eleven of thirty-two real questions — every single one from a client —
received no answer.** `how: gagged`, in 0.0 seconds.

    which cadence is active for us right now?
    how many senders are sending for us and what are their names?
    is ustwo.com in a campaign?
    what went out this week?
    Bruno pita jesmo li provukli struju. Reci mu...
    what's productive's email sending capacity?
    how many linkedin profiles do we have at the moment?
    what are the results so far?
    share daily summary please
    which three campaigns are awaiting my approval?
    what's waiting on my approval?

`CLIENT_CHANNEL_GAG` has been on since 2026-09-23 and is correct — it was
set after the agent reported three positive replies where the classifier
says zero. But the measurement it forces is this: **34% of real traffic is
client traffic, and the agent currently answers none of it.**

**It also means this audit cannot score the client half at all.** The
`terms` column below is `n/a` 32 times out of 32 — not because no answer
leaked, but because **no client answer exists to check**. Any claim that
client scoping is healthy rests on the adversarial sweep
(`test_the_client_scope_under_attack.py`, 921 probes), not on this replay.

---

## 2. LATENCY: THE OPERATOR'S TARGET IS 30s. THE MEASURED p95 IS 132s.

    p50   24.3s
    p95  132.3s
    max  176.0s

And it is almost perfectly linear in the number of tool calls:

| tool calls | n | median |
|---|---|---|
| 0 | 2 | **4.5s** |
| 1 | 2 | 13.3s |
| 2 | 1 | 94.1s |
| 3 | 4 | 60.6s |
| 4 | 1 | 107.3s |
| 5 | 11 | **108.3s** (max 176.0s) |

**Eleven of the twenty-one answered questions used the full five-call
budget**, and every one of those took over 82 seconds.

### 2a. Measured per tool — and one of the proposed fixes saves nothing

    knowledge pack        0.00s
    batch_state           0.00s     local read
    next_actions          0.00s     local read
    sends_today          21.72s     provider
    activity_this_week   44.81s     provider

**The knowledge pack is already free.** "Prebuilt pack after every restart"
was one of the three fixes proposed for this, and it would save **zero
seconds** — the pack is cached, rebuilds in 0.13s cold, and never appears in
a turn's cost. Building it would have been work with no measurable effect.

**100% of the latency is provider readbacks**, and the shape is serial HTTP:
`sends_today` reads up to 8 campaigns, each costing a `campaign` GET plus a
`scheduled_emails` GET. `activity_this_week` reads ten. Sixteen to twenty
sequential round trips, one after another.

So the two fixes that WOULD work are the other two named:

1. **A short readback cache.** `sends_today`, `activity_this_week`,
   `weekly_plan` and `lead_counts` all read the same campaigns within one
   turn, and a five-call turn reads some campaigns four times. A 60-second
   cache keyed on campaign id collapses that.
2. **Parallel campaign reads.** The per-campaign loop is embarrassingly
   parallel and nothing in it depends on the previous result.

**Ranked by measured impact, the cache is first** — it removes duplicate
reads *within* a turn, which is where the multiplication happens.

---

## 3. THE SCORES

| check | pass | fail | n/a |
|---|---|---|---|
| numbers | 31 | 1 | 0 |
| scope | 32 | 0 | 0 |
| terms | 0 | 0 | **32** |
| promise | 21 | 0 | 11 |
| language | 21 | 0 | 11 |
| length | 15 | **6** | 11 |

**Clean answers: 25 of 32** — but read that against §1: eleven of the
thirty-two are "clean" only because they are empty.

**Of the 21 answers that actually exist, 6 broke the length rule and 1
carried an unsupported number** — so **14 of 21 real answers were fully
clean, 67%.**

---

## 4. THE WORST TWENTY

### 4a. The eleven with no answer (worst, and all one cause)

Listed in §1. One cause: `CLIENT_CHANNEL_GAG`. Not a bug — a decision — but
it is the largest single defect in the agent's real behaviour today.

### 4b. The six that ran long

Every one is a "what is happening" question, and every one got **9–11
sentences and 1,036–1,594 characters** against a prompt asking for two to
six:

    10 sentences  1,263 chars   what is running
    10 sentences  1,323 chars   what are you working on ?
    11 sentences  1,538 chars   what can we do now ?
     9 sentences  1,195 chars   what is running right now, and which...
    10 sentences  1,036 chars   are you still processing leads?
    10 sentences  1,594 chars   What are you working on now?

**The pattern is exact and it is a cause, not six incidents:** a broad
question plans five tools, five readbacks produce a large material, and the
model summarises all of it. The length rule loses to the volume of material.
Fix at the plan, not the prompt — a broad question does not need five
readbacks, it needs the right one.

### 4c. The one unsupported number — the guard working

    q: how many customers do we have enrolled
    a: "Enrolled across the Productive workspace is 740 leads against 667
        sent lifetime..."
    guard: unsupported number(s): 73

The model produced a figure of `73` that was not in the material; the turn
**replaced the answer** rather than posting it. This is the number guard
doing exactly its job, and it is recorded here as a pass for the system even
though it scores as a fail for the answer.

### 4d. Two more worth naming

- **`where can I buy kebab?`** was answered in 2.8s, in an internal channel.
  Off-topic, harmless, and the right behaviour now that internal assistant
  mode exists.
- **`do we have any <name> inboxes in prod`** — 21.3s, answered. Note that
  the question names a real sender; the answer must not, and did not.

---

## 5. WHAT THIS AUDIT COULD NOT MEASURE, STATED PLAINLY

1. **Client answer quality — at all.** See §1. Zero client answers exist.
2. **The question catalogue contributed zero questions.** `--catalogue`
   parses `- "quoted line"` bullets and
   `docs/SLACK-AGENT-QUESTION-CATALOGUE.md` does not use that shape. **A
   harness defect, not an absence of questions** — the corpus is 32 live
   questions only, and the catalogue pass still has to be run.
3. **Correctness against provider truth was scored structurally, not
   semantically.** `numbers` reads the turn's own `guard`, which catches a
   figure absent from the material. It does **not** catch a figure that is
   present in the material and wrong, or the right number answering the
   wrong question — `what is running` answered with MONITOR HEALTH rather
   than campaigns is invisible to every check here.
4. **One run, one model, one evening.** Latency will vary with provider
   load.

---

## 6. THE FIXES, RANKED BY MEASURED IMPACT

1. **A 60-second readback cache keyed on campaign id.** Removes duplicate
   provider reads within a turn. Largest measured effect, no behaviour
   change, and the numbers stay the provider's own.
2. **Parallel per-campaign reads** in `sends_today`,
   `activity_this_week`, `weekly_plan`, `lead_counts`.
3. **Plan fewer tools for a broad question.** Fixes §4b's six length
   failures at the cause, and compounds with 1 and 2 by removing calls
   entirely.
4. **Lift the gag** — the operator's decision, gated on the three faults
   that caused it. Until then a third of real traffic is unanswered.
5. **Fix `--catalogue` parsing** and re-run, so the second corpus is
   actually measured.

**Not on this list: prebuilding the knowledge pack.** It was proposed and
it is already free. §2a.
