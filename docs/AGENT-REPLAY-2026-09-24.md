# The replay, after the latency work — and the bottleneck moved

33 real questions since 2026-09-21, replayed through their **original
channel and user**, live provider reads, live `claude-opus-5`, nothing
posted. Supersedes the latency half of `AGENT-REPLAY-2026-09-23.md`; its
scorecard sections still stand.

Run against `21222253` with `--lift-gag`. Production's `work/` was COPIED
and read; the live files were never written.

---

## 1. THE TARGET IS NOT MET, AND THAT IS THE HEADLINE

**Operator's target: p50 under 15s, p95 under 30s in CLIENT scope.**

| | target | measured |
|---|---:|---:|
| client p50 | 15s | **25.4s** |
| client p95 | 30s | **37.8s** |
| client max | — | 74.1s |

All 33: p50 26.6s, p95 37.8s, max 74.1s. Eleven of the 33 resolve to client
scope, which is the same eleven the 2026-09-23 run could not score at all.

---

## 2. WHAT DID CHANGE, AND IT IS MOST OF THE WAY

**The comparison that matters is not 24.3s → 26.6s.** The published
baseline p50 of 24.3s included **eleven gagged answers at 0.0 seconds**,
which is a median dragged down by questions that got no answer. Over the
21 questions the baseline actually ANSWERED, its median was **≈108s**
(reconstructed from its own tool-count table; 11 of those 21 took over 82
seconds).

Everything is answered now, so the honest comparison is:

| | 2026-09-23 | 2026-09-24 |
|---|---:|---:|
| turns over 82s | **11 of 21 answered** | **0 of 33** |
| p95 | 132.3s | **37.8s** |
| max | 176.0s | **74.1s** |
| median over answered | ≈108s | **26.6s** |

### 2a. The tool-count curve is flat now

    tools   n    2026-09-24      2026-09-23
      0     1        4.4s            4.5s
      1    10       26.2s           13.3s
      2     3       13.5s           94.1s
      3     8       26.0s           60.6s
      4     4       28.4s          107.3s
      5     7       35.7s          108.3s

A five-tool turn cost 108.3s and costs 35.7s. **The 1-tool row going 13.3s
to 26.2s is not a regression** — the broad-question route moved questions
INTO that row that used to be five-tool turns at 108s.

---

## 3. THE BOTTLENECK MOVED, AND THE OLD SENTENCE IS NOW FALSE

`AGENT-REPLAY-2026-09-23.md` says **"100% of the latency is serial provider
HTTP."** That was true when it was written. It is not true any more, and
anybody planning the next increment from it will optimise the wrong thing.

    a 0-tool turn                    4.4s     no provider read at all
    a 1-tool broad-route turn       26.2s
    `working_on` alone (A/B)         5.4s     the provider half of it

**So roughly 21 seconds of every turn is answer composition — one model
call — and it is untouched by this increment.** The provider work took a
five-tool turn from 108s to 36s; the model floor is what is left, and no
amount of caching or parallelism moves it.

The next latency increment is about the model: a smaller model for short
answers, streaming, or a shorter answer prompt. **Measure before building
to it** — that rule has now paid three times on this branch.

---

## 4. THE ONE OUTLIER, AND IT IS WORTH READING

    74.1s   5 tools   planned=model
    "Bruno pita jesmo li provukli struju. Reci mu..."

A Croatian client question that planned the full five tools and scored a
`numbers` failure. It is the only turn over 60s in the run and the only
thing standing between p95 37.8s and something near 30s. It is a relay -
somebody asking the agent to answer on behalf of a third person - and the
broad-question route does not catch it because it is genuinely specific.

---

## 5. THE SCORES, AND THE COLUMN THAT IS NO LONGER `n/a` 32 TIMES

| check | pass | fail | n/a |
|---|---|---|---|
| numbers | 31 | 2 | 0 |
| scope | 33 | 0 | 0 |
| terms | **11** | **0** | 22 |
| promise | 30 | 3 | 0 |
| language | 32 | 1 | 0 |
| length | 27 | 6 | 0 |
| subject | 10 | 1 | 22 |

**`terms` is 11 passes rather than 32 `n/a`.** The last audit could not
score client scoping at all, because no client answer existed to check —
and a column of `n/a` was at risk of being read as a column of passes.
Eleven real client answers were checked against the backstop and none
leaked.

`length` is 6 of 33 rather than 6 of 21 — the same six-ish failures over a
corpus half again as large, so proportionally better and not fixed. The
broad route was supposed to fix these and did not: five of the six are
turns that took the route and still answered long. **The plan was the
cause of the volume; it is not the whole cause of the length.** That is a
prompt problem and it is now separable from the plan, which it was not
before.

`clean answers: 23 of 33` — against 14 of 21 fully clean last time.

---

## 6. WHAT THIS RUN COST TO GET RIGHT

Three live runs, and the first two were wasted for reasons worth recording.

1. **The workspace roster was not copied.** The copy list said
   `workspaces.json`; the file is `workspaces.jsonl`. Without it **no
   question resolved to client scope** — 22 unbound, 11 internal, zero
   client — so `--lift-gag` did nothing and the run measured the scope the
   target is NOT stated in. One character. `CLAUDE.md`'s note that a
   worktree's own `work/` is stale and that client probes there resolve
   unbound is about exactly this.

2. **The second run measured pre-fix code** and was killed at 6 of 33
   rather than finish a number that would be discarded.

The replay is the only thing that finds this class of defect, which is the
argument for running it rather than trusting the suite: **the
broad-question route had eighteen green tests and fired ZERO times on real
traffic**, because every real question arrives as `<@U0C3CBAP6BB> what is
running` and the guard matched the `@`. No test could have caught it,
because every phrasing in them was invented.
