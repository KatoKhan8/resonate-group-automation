# Agent improvement plan — ranked by measured impact

**For the operator to pick from.** Ten items, ranked by what the
measurements of 2026-09-23 actually showed, not by what seemed likely.
Every rank cites its number and where it came from.

Sources: `docs/AGENT-REPLAY-2026-09-23.md` (32 real questions replayed),
`tests/test_the_client_scope_under_attack.py` (921 adversarial probes), and
the per-tool timing in §2a of the replay.

**Nothing here is started.** Items 1–3 are one increment each.

---

## THE RANKING AT A GLANCE

| # | what | measured basis | size |
|---|---|---|---|
| 1 | Lift the gag, gated | **11 of 32** real questions unanswered | operator |
| 2 | 60s readback cache | p95 **132s** vs 30s target | M |
| 3 | Parallel campaign reads | `activity_this_week` **44.8s** alone | M |
| 4 | Plan fewer tools for broad questions | **6 of 6** length failures share it | M |
| 5 | Semantic correctness scoring | audit **cannot** see a wrong-question answer | M |
| 6 | Fix `--catalogue`, re-run | second corpus scored **0** questions | S |
| 7 | Missed mentions on restart | 0 today, but unmeasured by construction | M |
| 8 | Meetings ledger command | `meeting` state has one hand-fed source | S |
| 9 | Promise scan | `promises` exists; nothing sweeps history | S |
| 10 | Deliverable requests | 1 of 32 real questions asked for one | M |

---

## 1. LIFT THE GAG — the largest defect, and only the operator can

**Measured: 11 of 32 real questions (34%) received no answer.** Every one
from a client. `how: gagged`, 0.0 seconds.

`CLIENT_CHANNEL_GAG` was set for three real faults: three positive replies
reported where the classifier says zero, an "awaiting your approval" that
was an operator decision, and a seven-minute turn. **Two of the three now
have mechanisms**:

- the positives: `replyverdict.positive_confirmed` is 0 until a verdict can
  be proved current, so the autoresponder cannot be announced;
- the seven minutes: **still true and worse than thought — p95 is 132s.**
  Items 2 and 3 are the precondition.

So the honest reading is that **the gag should lift after items 2 and 3,
not before**, and the third fault ("awaiting your approval") needs its own
check. Ranked first because it is the biggest number; sequenced after 2–3
because lifting it onto a 132-second turn recreates one of the faults that
caused it.

---

## 2. A 60-SECOND READBACK CACHE, KEYED ON CAMPAIGN ID

**Measured: p50 24.3s, p95 132.3s, max 176s, against a 30s target.**

    0 tools   4.5s        sends_today         21.72s
    5 tools 108.3s        activity_this_week  44.81s

100% of it is serial provider HTTP. **A five-call turn reads the same
campaign up to four times** — `sends_today`, `activity_this_week`,
`weekly_plan` and `lead_counts` all walk the same campaign list.

A per-process cache keyed on `campaign_id`, 60 seconds, collapses the
duplication **within one turn** without changing a single number: the values
are still the provider's own, just not re-fetched three times in ninety
seconds.

**Why first among the fixes:** it removes reads rather than making them
faster, and the duplication is where the multiplication happens.

**The risk to write into it:** a cache is a second representation of
provider truth, which is the thing this repository has been burned by. Keep
it short, per-process, never persisted, and stamp every cached readback with
the time it was actually fetched so a stale value is visible rather than
silent.

---

## 3. PARALLEL PER-CAMPAIGN READS

`sends_today` reads up to 8 campaigns, each a `campaign` GET plus a
`scheduled_emails` GET; `activity_this_week` reads ten. **Sixteen to twenty
sequential round trips.** Nothing in the loop depends on the previous
result.

Expected effect: `activity_this_week` from 44.8s toward the slowest single
campaign. Compounds with item 2 — the cache removes calls, this one overlaps
what remains.

**Bound the concurrency** and keep the provider's rate limit in view;
`CALLS_PER_MIN = 60` is documented in `stage_s3_icp`.

---

## 4. PLAN FEWER TOOLS FOR A BROAD QUESTION

**Measured: all 6 length failures are the same question shape** — "what is
running", "what are you working on", "what can we do now" — answered in
9–11 sentences and 1,036–1,594 characters against a prompt asking for two
to six.

The cause is not the prompt. A broad question plans five tools, five
readbacks make a large material, and the model summarises all of it. **The
length rule loses to the volume of material.**

`working_on` (shipped today) is the right answer to exactly these
questions and is one call. Route the broad shapes to it instead of fanning
out. This also compounds with 2 and 3 by removing calls entirely — likely
the largest latency win after the cache, from a change that is about
answer quality.

---

## 5. SCORE SEMANTIC CORRECTNESS, NOT JUST STRUCTURAL

**The audit's own blind spot, stated in its §5.** `numbers` reads the
turn's `guard`, which catches a figure **absent from the material**. It
cannot catch:

- a figure present in the material and wrong;
- the **right number answering the wrong question**.

The first live question in the log is `what is running`, answered with
**monitor health** — six watchers beating — when the asker plausibly meant
campaigns. **Every check in the replay scores that answer clean.**

This needs a small expected-answer set: twenty questions with the tool that
should have been called. Cheap, and it converts the replay from a leak
detector into a quality measure.

---

## 6. FIX `--catalogue` AND RE-RUN — S

`catalogue_questions()` matches `- "quoted line"`;
`SLACK-AGENT-QUESTION-CATALOGUE.md` does not use that shape, so the second
corpus scored **zero** questions. A defect in the harness, not an absence of
questions. Until it is fixed, the audit's corpus is 32 questions rather than
32 plus the mined catalogue.

---

## 7. MISSED MENTIONS ON RESTART — M

On start, answer mentions since the last heartbeat that nobody answered.

**Ranked seventh on honesty rather than evidence:** the replay found no
example, but it *could not* — it reads questions the agent already logged,
and a missed mention is by definition one that never reached the log. The
measurement to take first is a sweep of `#resonate-os` history against
`work/slack-agent.jsonl` for mentions with no `answered` row.

---

## 8. THE MEETINGS LEDGER COMMAND — S

`meeting booked <domain> <date>`. `MEETING` is one of the operator's eight
account states and its only source is a hand-fed ledger, so the state is
only as good as somebody remembering to write to it. Small, self-contained,
and it makes one of the eight states real.

---

## 9. PROMISE SCAN OVER THE LAST 7 DAYS — S

`promises` answers what was promised **and logged**. Nothing sweeps channel
history for a promise the agent made before the mechanism existed. One pass
over `#resonate-os`, reconciled against `slackpromises`.

---

## 10. DELIVERABLE REQUESTS — M

"Make me a list / document" produces a file in thread when the data is
theirs and read-only, else a ticket.

**Ranked last on measured demand: one of 32 real questions asked for one**
("share daily summary please" — and it was gagged). Worth building, but
items 1–4 affect every question and this one affects roughly 3%.

---

## WHAT IS DELIBERATELY NOT ON THIS LIST

**Prebuilding the knowledge pack.** It was proposed as a latency fix and it
is already free — 0.00s in a turn, 0.13s to rebuild cold. It would have been
real work with no measurable effect, and it is named here so it is not
proposed again.
