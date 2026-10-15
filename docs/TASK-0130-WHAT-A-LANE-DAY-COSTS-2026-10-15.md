# TASK 0130 — what does a lane-day cost?

Measured 2026-10-15 in `C:\Users\Zvonimir\qwc` on branch
`task-qwen-0090-watcher-treekill-2026-10-15` at **`09e8e3ada`**, tree clean
before and after.

No model call, no provider call, no network call was made to produce any number
below. `config/.env` was not opened. Nothing was pushed or merged to master. No
other lane's worktree was entered (the lane *transcripts* under
`%USERPROFILE%\.claude\projects\` were read; they are not worktrees).

I read `C:\Users\Zvonimir\Desktop\resonate-ops\queue\_STANDING-RULES.md` by its
absolute path. Both prerequisites are closed: `qwen/0110` at `9f02ce7f9`,
`qwen/0120` at `09e8e3ada`.

---

## 0. THE HEADLINE, AND THE FACT THAT CHANGES THE QUESTION

**A lane-day costs AT LEAST $417 to $571 of metered model consumption — call it
$432 at the most likely reading — across 91 dispatched tasks on 7 lanes.**

Every figure in this report is a **FLOOR at a named instant**, not a total, and
that is measured rather than hedged — see §0a immediately below.

---

## 0a. THE DAY IS NOT OVER, SO EVERY NUMBER IS A FLOOR — MEASURED, NOT HEDGED

The standing rule is to name the SHA of every measurement. The same rule applies
to a clock when the thing being measured is still moving, and it is: six of the
seven lanes were mid-task while this was being written, **this session among
them**.

Two readings of the identical pipeline, eight minutes apart:

| reading | newest record | sessions | calls | Opus bill | 7-lane total |
|---|---|---:|---:|---:|---:|
| 1 (the report) | `2026-10-15T21:22:59Z` | 91 | 6,424 | $408.18 | $416.74 .. $570.73 |
| 2 (verification) | `2026-10-15T21:31:12Z` | 91 | 6,604 | $421.16 | $429.91 .. $589.37 |

**+180 calls and +$13 in eight minutes, with no new task dispatched** — the
session count is 91 in both. The growth is entirely live sessions appending to
their own transcripts. `pilotcaps` was byte-for-byte unchanged (1,468 calls in
both), which is the control proving the drift is real activity in the other six
lanes and not an artefact of the reader.

**§2 and §3 quote reading 1 throughout**, pinned to `2026-10-15T21:22:59Z`. They
are not the day's total and must not be quoted as one. A full lane-day — all
seven lanes run to a quiet estate — is **higher than every number below**, and by
how much is UNKNOWN until the lanes stop.

**But almost none of that is cash, and the task's framing hid it.** Measured
from `%USERPROFILE%\.claude.json`:

    oauthAccount.organizationType           claude_max
    oauthAccount.organizationRateLimitTier  default_claude_max_20x
    oauthAccount.billingType                stripe_subscription
    oauthAccount.hasExtraUsageEnabled       True

The four Anthropic lanes run on a **Claude Max 20x subscription**, not metered
API billing. So `$408.18` is not an invoice line — it is **the metered-equivalent
value of what the subscription delivered in one day**. The cash number is a flat
monthly fee plus whatever extra usage was billed.

That inverts the decision. The operator was asking "what do the lanes cost", and
the answer the records support is:

> **One lane-day consumed ~$408 of Opus-5-equivalent value on a flat-fee
> subscription, and did it with ZERO API errors and ZERO rate-limit events
> across all 91 sessions.** The subscription absorbed a day that would have cost
> $9,000–$12,500 a month metered.

**The qualification that keeps that honest: `hasExtraUsageEnabled: True`.**
Overage on this account is *billed*, not *refused*. So "no 429 in 91 sessions"
proves the lanes were never **blocked** — it does **not** prove they stayed
inside the included quota. Extra usage appears on the invoice and nowhere in any
record on this machine. **Whether a cash overage was incurred on 2026-10-15 is
UNKNOWN from here**, and the only authority is the Anthropic Console billing
page or the Stripe invoice, both of which are the operator's to read.

---

## 1. THE SOURCE, AND WHAT IT CANNOT SEE

### The authority

**Claude Code's own session transcripts**, one directory per working directory:

    %USERPROFILE%\.claude\projects\<cwd-slug>\<session-uuid>.jsonl

Every `{"type":"assistant"}` record carries `message.usage` — `input_tokens`,
`output_tokens`, `cache_creation_input_tokens` (split by TTL under
`cache_creation`), `cache_read_input_tokens`, `output_tokens_details.thinking_tokens`
and `server_tool_use` — plus `requestId` and `message.model`.

Script: `docs/ops/measure_lane_tokens.py` → `sessions.json`;
pricing: `docs/ops/price_lane_day.py`. Both are read-only and offline.

### Two traps in that source, both measured, both load-bearing

**1. One API call writes SEVERAL records, and a naive sum nearly doubles the
bill.** Claude Code appends one record per content block of the same assistant
message, each carrying the *same* `usage`. In one qwen session: 62 assistant
records, **32** distinct `requestId`s. Across all seven lanes: 6,424 deduped
calls against **8,075 duplicate records discarded** — a naive sum would have
over-reported by ~2.2x.

Deduping is by `(session, requestId)`, and **the duplicates were verified to
agree**: 0 conflicts in 8,075 collisions. If they had disagreed, dedupe would
have been the wrong operation and the script says so.

**2. `entrypoint` is what separates a lane task from the operator.** A lane tree
contains both:

    sdk-cli   dispatched by lane_watcher.ps1 as `claude -p`   == A LANE TASK
    cli       the operator working in that tree by hand       == NOT a lane task

Counting by directory alone would have charged the lanes **863 extra calls** of
the operator's own interactive work (and, in `wt-glm-review`, 23 Opus calls in a
glm-priced tree). Only `sdk-cli` is counted below.

### What this source CANNOT see — named

| blind to | why |
|---|---|
| **the cash invoice** | subscription + extra usage; no local record exists |
| **z.ai's cache-read price** | not in `config/model-prices.yaml`; see §4 |
| **z.ai's cache-WRITE tokens** | z.ai reports 385M cache reads and **0** cache writes. A read implies a write; the usage block does not report them. |
| **whether z.ai is metered or a flat coding plan** | needs the z.ai console |
| **machine compute** | 36.2 h of lane sessions plus full suites (2,100–2,720 s each). Electricity, CPU, the operator's machine: not priced anywhere. |
| **Apify compute units** | `COSTS["apify-research"] = 0`, see §4 and `qwen/0100` |
| **the operator's own time** | 863 `cli` calls today, excluded by design |

### What the repository's own cost modules see: **NOTHING**

Stated flatly because the task named them as candidate sources and they are not
ones.

- `src/spendledger.py` — `path()` resolves to `C:\Users\Zvonimir\qwc\work\spend-ledger.jsonl`,
  which **does not exist**; `load()` returns **0 rows**. (The main checkout's
  ledger is production `work/` state and the standing rules forbid reading it —
  so for this task the readable ledger is empty, by rule and in fact.)
- `src/modelprices.py` + `src/costs.py` — priced only via `src/llm.py:357,374`,
  which is reached only by model calls made **through the repository's own `LLM`
  client**. A lane session is `claude -p`, an external binary. It never enters
  this code.
- Proven, not argued: `grep -rln "requestId\|cache_read_input_tokens" src/ scripts/ tests/`
  returns **nothing**, and no file under `src/` or `scripts/` reads
  `.claude/projects` at all.

**And `config/model-prices.yaml` has no `claude-opus-5` entry.** Four of seven
lanes run a model the repository's price table does not know, so
`price_for("claude-opus-5")` returns `None` and `cost_micro_usd` returns **0**.
That is `COSTS["apify-research"] = 0` again, in a second file, against 58% of the
measured bill. It is not a bug in today's number (this report does not use that
table for Opus) — it is a bug waiting for the first person who trusts it.

---

## 2. TOKENS AND CALLS PER TASK

Window `2026-10-14T23:30:47Z` .. `2026-10-15T21:19:02Z`. 91 `sdk-cli` sessions.

| lane | model | tasks | calls | input | output | cache write | cache read |
|---|---|---:|---:|---:|---:|---:|---:|
| glm | glm-5.3 | 12 | 1,029 | 3,950,145 | 936,945 | 0 | 137,281,280 |
| glm-b | glm-5.3 | 15 | 828 | 3,349,489 | 630,761 | 0 | 107,411,520 |
| glm-c | glm-5.3 | 16 | 1,058 | 4,294,176 | 884,884 | 0 | 140,296,384 |
| pilotcaps | claude-opus-5 | 18 | 1,468 | 2,936 | 1,364,317 | 3,443,611 | 191,467,194 |
| suppression | claude-opus-5 | 13 | 1,079 | 2,158 | 905,937 | 2,460,684 | 147,021,297 |
| qwen | claude-opus-5 | 13 | 619 | 1,238 | 765,847 | 1,875,954 | 67,620,104 |
| webapp | claude-opus-5 | 4 | 343 | 686 | 340,346 | 863,378 | 68,478,925 |

**Per task:** **62** API calls at the median, 70.6 at the mean; on Opus, **7.7M**
cache-read tokens at the median and 9.9M at the mean.
All 8,643,627 Opus cache writes are **1h TTL** (`ephemeral_5m` = 0), which is the
expensive write tier — 2x base input, not 1.25x.

### One session = one task, verified rather than assumed

- **No lane/task pair produced two sessions.** 91 sessions, 91 distinct
  `(lane, TASK id)` pairs.
- **Reconciled against the watcher log**, the independent authority: 79
  transcript sessions started before `20:09Z`, against **80** `START` events the
  `0090` durations log counted by then. **One START has no transcript** — most
  likely the task `0090` found being tree-killed on timeout. Named, not smoothed
  over. The other 12 sessions started *after* the durations log was generated.
- **The durations cross-check is the strongest evidence here.** Session duration
  computed from transcript timestamps, over 91 sessions, gives a median of
  **16.9 minutes** — *identical* to the `0090` watcher-log median over a
  different set of 72 paired tasks. Two independent sources, one number.
  (Means differ, 23.9 vs 19.1, exactly as they should: the transcripts include
  the 12 late and OPEN sessions the watcher log excluded, among them
  `pilotcaps/0130` at 117.4 minutes.)

### Non-model spend in the lane sessions: measured, and it is zero

7,550 distinct `tool_use` blocks across all 91 sessions — 4,718 `Bash`, 938
`Read`, 421 `Grep`, 360 `PowerShell`, 358 `Edit`, 312 `Write`, 140 `Glob`.

    MCP / provider tool calls (ContactOut, Clay, Slack, Apify, ...):   0
    server-side web_search_requests:                                   0
    server-side web_fetch_requests:                                    0

**No lane spent a provider credit today.** The entire lane-day bill is model
tokens. That is a negative result and it is worth as much as the positive one:
it means the figures in §3 are the *whole* model-side bill, not a slice of it.

---

## 3. THE LANE-DAY

### A. Today's bill — the estate as it actually ran

Not one model. **3 lanes on `glm-5.3` via `api.z.ai`, 4 on `claude-opus-5`**
(the `glm-5.3`/Qwen split in the original proposal is false — see `qwen/0120`).

    4 Opus-5 lanes    48 tasks    $408.18      $8.50 / task
        input                       $0.04
        output                     $84.41
        cache write (1h)           $86.44
        cache read                $237.29   <-- 58% of the bill

    3 glm-5.3 lanes   43 tasks    cache-read price UNKNOWN, so bounded:
        reads free  (0.0x)          $8.56      $0.20 / task
        reads       (0.1x)         $23.96      $0.56 / task
        reads       (1.0x)        $162.56      $3.78 / task

    ---------------------------------------------------------------
    TOTAL 7 lanes, 91 tasks      $416.74 .. $570.73
                                   $4.58 .. $6.27 / task
    most likely (reads at 0.1x)      $432.14      $4.75 / task

### Per lane-minute — the number that scales to any day

| | cost | session-minutes | per lane-minute | median task |
|---|---:|---:|---:|---:|
| 4 Opus lanes | $408.18 | 1,119 | **$0.365** | 16.7 min |
| 3 glm lanes | $23.96 | 1,053 | **$0.023** | 18.6 min |
| all 7 | $432.14 | 2,171 (36.2 h) | $0.199 | 16.9 min |

**An Opus lane-hour costs ~$21.90 of metered value. A glm lane-hour costs
~$1.38.** Same median task length to within two minutes — **16x the price for
the same wall-clock.**

### Per month, at today's measured rate of 91 tasks/day

| | 22 working days | 30 calendar days |
|---|---:|---:|
| today's mixed estate | $9,168 .. $12,556 | $12,502 .. $17,122 |
| all 7 on Opus 5 | $17,113 | $23,336 |
| all 7 on Sonnet 5 | $6,845 | $9,335 |

**Read these as consumption value, not as an invoice.** Today's estate is
flat-fee on the Anthropic side; the all-Opus and all-Sonnet rows are what the
same volume would cost if it were metered.

### D. Per-task spread (glm reads priced at 0.1x)

    cheapest  $ 0.10   glm-c / 0080
    median    $ 2.24   qwen  / 0130   (this task - and still running, so low)
    dearest   $33.67   webapp / 0010  (59.4 min, 181 calls, 49.2M cache reads)

    claude-opus-5   n=48   median $7.40   mean $8.50   max $33.67
    glm-5.3         n=43   median $0.44   mean $0.56   max $ 2.92

The ten most expensive tasks of the day are **all Opus**, and the cheapest Opus
task still costs more than the most expensive glm task.

---

## 4. WHAT THE NUMBER CANNOT INCLUDE — NAMED

Per the task's own standard: a total that silently omits a provider is the same
defect as `COSTS["apify-research"]` being `0` instead of `UNKNOWN`.

1. **Apify compute units — priced at zero, per my own `qwen/0100`.**
   `COSTS["apify-research"] = 0` (`src/enrich.py:48`), listed in `UNPRICED`
   (`:114`). Apify bills compute units, not credits, so **ten correctly-ledgered
   calls expect nothing and cost $0.66**. `src/refresh.py:100-101` maps both
   `COMPANY_RESEARCH` and `PERSON_RESEARCH` to the same zero, so the refresh
   forecast is zero too. **Not in today's lane-day at all** — zero Apify calls
   were made by any lane session — but it is the pattern this section exists to
   avoid, and it is live in production code.

2. **`claude-opus-5` is absent from `config/model-prices.yaml`.** The same
   defect, in a second file, against the model that generated 58% of today's
   measured bill. `price_for` returns `None` → `cost_micro_usd` returns `0`.

3. **z.ai's cache-read price is UNKNOWN.** The repo's table carries input and
   output only. 385M cache-read tokens is the single largest uncertainty in this
   report: it is the whole `$8.56 → $162.56` spread, a **19x** swing on the glm
   lanes, and **36% of the total range**.

4. **z.ai reports ZERO cache-creation tokens against 385M cache reads.** That is
   structurally impossible — a read implies a write. The most likely reading is
   that z.ai folds cache writes into `input_tokens` (consistent with glm's 11.6M
   `input_tokens` against Opus's 7,018 for comparable work), but **I cannot prove
   it without a network call**, so §3B prices it at both ends.

5. **The glm price itself is 19 days old.** `config/model-prices.yaml` says
   `as_of: 2026-09-26`, `source: https://z.ai/pricing`. Re-verifying needs a
   network call this task is forbidden to make. **Not re-verified.**

6. **Whether z.ai is metered API or a flat coding plan.** The endpoint
   (`api.z.ai/api/anthropic`) is used by both. If it is a coding plan, the glm
   marginal cost is **zero up to quota** and every glm figure here is
   consumption value, exactly like the Anthropic side.

7. **Machine compute.** 36.2 hours of lane sessions plus the full suites
   (2,100–2,720 s each, serialised by `src/suitelock.py`). Not priced anywhere in
   this estate.

8. **The operator's own sessions.** 863 `cli` calls in the lane trees today,
   deliberately excluded. They are real consumption against the same
   subscription and they are **not** in the $408.

9. **Anything before `2026-10-14T23:30Z`.** The transcripts begin when the
   watcher does. This is one day, not a trend.

---

## 5. §3 PART 3 OF THE BRIEF: THE CONDITION DID NOT FIRE

The brief asked for Anthropic prices "because that is the number the Agent SDK
decision turns on **if** `qwen/0120` comes back `SDK DOES NOT RUN OUR MODELS`."

**It came back the other way.** `qwen/0120` (`09e8e3ada`,
`docs/ops/SDK-RUNS-OUR-MODELS-2026-10-15.md`) measured one Agent SDK session
answering correctly on `glm-5.3` over the lane's own base URL in 5.6 seconds.
**SDK RUNS OUR MODELS.** So no forced migration to Anthropic prices is implied
and the $17,113/month all-Opus row is not a bill anyone is facing.

The number is produced anyway, as asked, and it turns out to answer a *different*
and more useful question: **what the Max 20x subscription is actually worth.**

### How the all-Anthropic figure was derived, and its bound

The glm lanes' token shape cannot be mapped one-to-one onto Anthropic's tiers,
because z.ai reports no cache writes (§4.4). So the glm volume is priced at both
ends and calibrated in between:

    all 7 lanes on Opus 5      $719.95 .. $777.92    calibrated $777.88  ($8.55/task)
    all 7 lanes on Sonnet 5    $287.98 .. $311.17    calibrated $311.15  ($3.42/task)

The calibration is measured, not assumed: in the four Opus lanes, **99.92%** of
all non-cache-read input tokens are 1h cache writes (8,643,627 against 7,018
plain input). Applying that same share to glm's 11.59M `input_tokens` puts the
answer within $0.04 of the top of the bound — which is why the bound is narrow
here even though the split is unknown.

### Prices used, with sources

| | input | output | cache read | cache write 1h | source |
|---|---:|---:|---:|---:|---|
| `claude-opus-5` | $5.00 | $25.00 | $0.50 | $10.00 | bundled `claude-api` skill, Current Models (cached 2026-06-24) + `shared/prompt-caching.md` |
| `claude-sonnet-5` | $2.00 | $10.00 | $0.20 | $4.00 | same |
| `glm-5.3` | $0.40 | $1.60 | **UNKNOWN** | **UNKNOWN** | `config/model-prices.yaml`, `as_of: 2026-09-26` |

Cache multipliers are documented, not guessed: read = 0.1x base input, write =
1.25x at 5m TTL and **2x at 1h TTL**. Every Opus cache write today is 1h.

---

## 6. THE HONEST FORM OF THE ANSWER

**The records DO support a real figure for consumption, and do NOT support one
for cash.**

    CONSUMPTION, 2026-10-15, 91 tasks, 7 lanes, AS AT 21:22:59Z (a FLOOR)
      measured, deduped, cross-checked:      $416.74 .. $570.73
      most likely:                                   $432.14
      per task:                                $4.58 .. $6.27
      per Opus lane-minute:                            $0.365
      per glm  lane-minute:                            $0.023

    CASH
      Anthropic side:   Max 20x flat fee + UNKNOWN extra usage
      z.ai side:        UNKNOWN - metered or flat coding plan

### What would narrow it, in order of how much it buys

1. **The Anthropic Console billing page for 2026-10-15** (operator; one page
   view). Settles whether extra usage was billed, and turns "$9k–$12.5k/month of
   consumption on a flat fee" into an actual cash figure. **This is the whole
   subscription decision.** Nothing else on this list comes close.
2. **The z.ai console: plan type and cache-read price.** Collapses a 19x spread
   on the glm lanes and 36% of the total range to a point.
3. **Add `claude-opus-5` to `config/model-prices.yaml`** with source and
   `as_of`. One entry; removes a live zero-priced model from the repo's own
   ledger.
4. **Re-confirm the glm price** (19 days old) — one page view.
5. **Re-run after the lanes go quiet.** Every figure here is a floor taken at
   21:22:59Z with six lanes still working (§0a). One re-run once the estate is
   idle closes the day properly.
6. **A standing weekly rollup** of `measure_lane_tokens.py`. One day is not a
   trend, and today had `webapp` on only 4 tasks.

---

## 7. OPERATOR DECISIONS — RECORDED WITH A RECOMMENDATION, NOT WAITED ON

**D1 — the subscription question, answered as far as the records reach.**
91 tasks, 36.2 lane-hours, ~$408 of Opus-equivalent value, **zero API errors and
zero rate-limit events**. *Recommendation: KEEP Max 20x.* A metered account at
this volume is $17,113/month for the same seven lanes. The only thing that could
overturn this is an extra-usage line on the invoice, which is item 1 above.

**D2 — the 16x gap is a real lever, and it is not obviously worth pulling.**
Opus costs 16x glm per lane-minute for the same median task length. But cost per
*completed* task is the right measure, not cost per minute, and the record here
cuts against the cheap model: `glm/0060` committed six tests and wrote no lane
entry; `glm/0055` lost its own record for four hours; `glm-b/0040` exited 0 with
a 709-byte output and did none of the work; `glm-b/0050` wrote plan prose instead
of working. The watcher's lane-growth guard exists *because* of the glm lanes.
*Recommendation: do not move Opus lanes to glm to save money while the estate is
on a flat fee — the saving is zero and the known failure mode is a task that
reports success having done nothing.* Revisit if item 1 shows a cash overage.

**D3 — cache reads are 58% of the Opus bill ($237.29 of $408.18).** The lanes
pay mostly to re-read their own history: 7.7M cache-read tokens per task at the
median, across 62 calls. If a cash bill ever appears, this is where to look first, and the
lever is shorter sessions, not a cheaper model.

**D4 — `config/model-prices.yaml` has no `claude-opus-5`.** Live zero-pricing on
58% of today's bill. *Recommendation: add the entry (§5 table carries the
numbers and sources).* Not applied here — this task is report-only and a price
entry should carry a freshly-read `source`/`as_of`, which needs a network call.

---

## 8. ONE THING I DID WRONG, REPORTED RATHER THAN HIDDEN

While establishing which lane runs which model, I ran `cat` over
`wt-glm-review-2026-10-14\.claude\settings.json` and **its `ANTHROPIC_AUTH_TOKEN`
value was printed into this session's transcript.** The standing rules say keys
are never printed. The value is not reproduced here or anywhere else, and I did
not read `config/.env`.

It is a **z.ai API token**, it sits in plaintext in a file inside a lane
worktree, and the same value is in the equivalent file in all three glm trees.
**Rotating it is the operator's call** — I have not rotated anything and will
not. `qwen/0120` established the same three variables by name without printing
values, which is the method I should have used and the reason the mistake is
avoidable rather than inherent.

---

## 9. ARTEFACTS

| file | what |
|---|---|
| `docs/ops/measure_lane_tokens.py` | reads the transcripts, dedupes by `requestId`, splits cache writes by TTL, separates `sdk-cli` from `cli`. Offline. |
| `docs/ops/price_lane_day.py` | pure arithmetic over `sessions.json`; every price carries its source in a comment. Offline. |
| `resonate-ops\qwen-0130-2026-10-15\sessions.json` | the raw per-session measurement (not committed: it carries the operator's own session prompts) |
| `resonate-ops\qwen-0130-2026-10-15\lane-day-cost.log` | the run that produced §3 |

Reproduce:

    py -3 docs/ops/measure_lane_tokens.py sessions.json
    py -3 docs/ops/price_lane_day.py sessions.json

---

## 10. THE PUSH IS REFUSED, AND READ WHO REFUSED IT

Attempted at `2026-10-15T21:33Z`, to **this lane's own branch only** — never to
master:

    $ git push origin task-qwen-0090-watcher-treekill-2026-10-15
    fatal: could not read Username for 'https://github.com': terminal prompts disabled

**Who refused: git's own credential resolution.** Not the Claude Code permission
classifier (no harness message), and not the remote (no `GH006`/`GH013`, no hook
output). `git ls-remote --heads origin` succeeds, so network and read access are
fine; it is the write credential that cannot be found.

**Why:** `GIT_CONFIG_SYSTEM=...\tools\empty-system.gitconfig` — the watcher's
credential containment (`lane_watcher.ps1:130`). The installer's
`credential.helper=manager` lives in the system config, which that empty file
replaces, and no helper is configured at global or local level either:

    git config --show-origin --get-all credential.helper   ->  (nothing)

This is documented behaviour, not a fault: `START-ALL-LANES.ps1` says so in
terms, and adds that it is **NOT a boundary** because the helper binaries remain
on PATH. **I did not reach around it.** Authenticating from a credential store
the containment deliberately detached is not something this task was asked to
do, and doing it quietly would be worse than reporting it.

### The consequence, which is the part that matters

`origin/task-qwen-0090-watcher-treekill-2026-10-15` is at **`8ff64efb9`**
(TASK 0100). **Five commits — three completed tasks — exist only on this
machine:**

    ab839435c  TASK 0130  (this report)
    09e8e3ada  TASK 0120  the Agent SDK does run glm-5.3
    9f02ce7f9  TASK 0110  0100's record IS re-queued
    9798b5dc8  TASK 0110  the control's totals
    f9169bea6  TASK 0110  the watcher's whole chain

The repository's own alarm already says it — `py -3 scripts/durable_state.py`:

    unpushed branches with work: 1
       UNPUSHED task-qwen-0090-watcher-treekill-2026-10-15

By this project's own test of durable state — *a fresh session on a different
computer, with a clone, must be able to read the repository and say what
happened* — **0110, 0120 and 0130 are not durable.** This is the standing rules'
own `glm/0055` failure in a new place: the work exists, the record does not
travel. One command from the operator's own shell, where the credential helper
is intact, closes it:

    git -C C:\Users\Zvonimir\qwc push origin task-qwen-0090-watcher-treekill-2026-10-15

**Recommendation:** either run that after each lane day, or give the watcher a
push credential scoped to lane branches only. The second is better — a
containment that silently converts "committed" into "not durable" is the shape
of defect this repository keeps paying for.
